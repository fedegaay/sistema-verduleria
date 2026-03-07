import streamlit as st
from supabase import create_client, Client
import pandas as pd
import time
from datetime import timedelta, datetime
from fpdf import FPDF
import unicodedata

# --- CONFIGURACIÓN DE CONEXIÓN ---
URL = "https://gosjojpueocxpyiqhvfr.supabase.co"
KEY = "sb_publishable_rZUwiJl548Ii1CwaJ87wLw_MA3oJzjT"
supabase: Client = create_client(URL, KEY)

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="El Rey Verdu - Pedidos", layout="centered")

# --- ELIMINAR ANCLAS Y ESTILOS ---
st.markdown("""
    <style>
    .stToolbarActionButton { display: none; }
    h1 a, h2 a, h3 a, h4 a, h5 a, h6 a { display: none !important; }
    [data-testid="stHeader"] {background: rgba(0,0,0,0);}
    
    /* Encabezados de tabla */
    .tabla-header {
        font-weight: bold;
        background-color: #2e7d32;
        color: white;
        padding: 8px;
        border-radius: 4px;
        text-align: center;
        margin-bottom: 10px;
        font-size: 0.9rem;
    }
    
    /* Forzar teclado numérico en móviles (no siempre efectivo en Streamlit) */
    input[type="text"] {
        inputmode: decimal !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIONES DE SOPORTE ---
def normalizar_texto(texto):
    """Limpia caracteres no compatibles con FPDF (acentos y otros)"""
    if not texto: return ""
    return "".join(c for c in unicodedata.normalize('NFKD', str(texto)) if unicodedata.category(c) != 'Mn')

def validar_cantidad(valor):
    """Fuerza a que el número sea entero o termine en .5"""
    try:
        if valor is None or str(valor).strip() == "": return 0.0
        num = float(str(valor).replace(',', '.'))
        return round(num * 2) / 2
    except:
        return 0.0

def check_session():
    if "user_id" in st.query_params and "user_info" not in st.session_state:
        u_id = st.query_params["user_id"]
        try:
            res = supabase.table("usuarios").select("*").eq("id", u_id).execute()
            if res.data:
                st.session_state["user_info"] = res.data[0]
        except Exception:
            pass

def obtener_maestro_productos():
    res = supabase.table("productos_lista").select("nombre, orden, id").order("orden").execute()
    return pd.DataFrame(res.data)

# --- FUNCIONES PARA GENERAR PDF (CON CORRECCIÓN DE BYTES) ---
def generar_pdf(titulo, datos):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(190, 10, normalizar_texto(titulo), ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(90, 8, "Producto", 1)
    pdf.cell(40, 8, "Cant.", 1)
    pdf.cell(60, 8, "Unidad", 1, ln=True)
    pdf.set_font("Arial", "", 12)
    for _, row in datos.iterrows():
        pdf.cell(90, 8, normalizar_texto(row['Producto']), 1)
        pdf.cell(40, 8, f"{float(row['Total']):.1f}", 1)
        pdf.cell(60, 8, normalizar_texto(row['Unidad']), 1, ln=True)
    
    return bytes(pdf.output(dest='S'))

def generar_pdf_detallado(titulo, datos):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(190, 10, normalizar_texto(titulo), ln=True, align="C")
    pdf.ln(10)
    
    sucursales = datos['usuarios.nombre_sucursal'].unique()
    for sucursal in sucursales:
        pdf.set_font("Arial", "B", 14)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(190, 12, f"SUCURSAL: {normalizar_texto(sucursal)}", 1, ln=True, fill=True)
        pdf.set_font("Arial", "B", 10)
        pdf.cell(100, 8, "Producto", 1)
        pdf.cell(45, 8, "Cantidad", 1)
        pdf.cell(45, 8, "Unidad", 1, ln=True)
        pdf.set_font("Arial", "", 11)
        datos_sucursal = datos[datos['usuarios.nombre_sucursal'] == sucursal]
        for _, row in datos_sucursal.iterrows():
            pdf.cell(100, 8, normalizar_texto(row['producto']), 1)
            pdf.cell(45, 8, f"{float(row['cantidad']):.1f}", 1)
            pdf.cell(45, 8, normalizar_texto(row['unidad_medida']), 1, ln=True)
        pdf.ln(10)
    
    return bytes(pdf.output(dest='S'))

def guardar_pedido(usuario_id, dict_pedidos, dict_unidades, lista_extras):
    batch = []
    # Productos de lista fija con validación ,5
    for prod, cant_str in dict_pedidos.items():
        cant = validar_cantidad(cant_str)
        if cant > 0:
            batch.append({
                "usuario_id": usuario_id, "producto": prod, 
                "cantidad": cant, "unidad_medida": dict_unidades.get(prod, "cajon/es"),
                "estado": "pendiente"
            })
    # Productos adicionales (Extras) con validación ,5
    for extra in lista_extras:
        cant_ex = validar_cantidad(extra['cantidad'])
        if extra['nombre'] and cant_ex > 0:
            batch.append({
                "usuario_id": usuario_id, "producto": extra['nombre'].strip().capitalize(),
                "cantidad": cant_ex, "unidad_medida": extra['unidad/es'],
                "estado": "pendiente"
            })
    
    if batch:
        supabase.table("pedidos").insert(batch).execute()
        st.session_state.cantidades = {} # Limpiamos para el reset
        st.session_state.extras = [] 
        st.session_state.reset_count = st.session_state.get('reset_count', 0) + 1
        return True
    return False

def reordenar_producto(prod_id, orden_actual, direccion, df_completo):
    if direccion == "up" and orden_actual > 0:
        target_index = orden_actual - 1
    elif direccion == "down" and orden_actual < len(df_completo) - 1:
        target_index = orden_actual + 1
    else: return
    
    match = df_completo[df_completo['orden'] == target_index]
    if not match.empty:
        target_id = match.iloc[0]['id']
        supabase.table("productos_lista").update({"orden": target_index}).eq("id", prod_id).execute()
        supabase.table("productos_lista").update({"orden": orden_actual}).eq("id", target_id).execute()
        st.cache_data.clear()

# --- LÓGICA DE INICIO ---
check_session()

if "user_info" not in st.session_state:
    st.markdown("<h1 style='text-align: center;'>📍 El Rey Verdu 📍<br>Pedidos</h1>", unsafe_allow_html=True)
    with st.form("login"):
        u = st.text_input("Usuario")
        p = st.text_input("Clave", type="password")
        if st.form_submit_button("Iniciar Sesión", type="primary", use_container_width=True):
            res = supabase.table("usuarios").select("*").eq("username", u).eq("password", p).execute()
            if res.data:
                st.session_state["user_info"] = res.data[0]
                st.query_params["user_id"] = res.data[0]["id"]
                st.rerun()
            else: st.error("Acceso denegado")
else:
    info = st.session_state["user_info"]
    
    # Barra superior
    c_suc, c_out = st.columns([0.7, 0.3])
    with c_suc: st.markdown(f"### 📍 {info['nombre_sucursal']}")
    with c_out:
        if st.button("Cerrar Sesión", type="secondary", use_container_width=True):
            st.session_state.clear()
            st.query_params.clear()
            st.rerun()

    df_maestro = obtener_maestro_productos()
    lista_prod_nombres = df_maestro['nombre'].tolist()
    
    # Inicialización de estados de sesión
    if "cantidades" not in st.session_state: st.session_state.cantidades = {}
    if "unidades_sel" not in st.session_state: st.session_state.unidades_sel = {}
    if "extras" not in st.session_state: st.session_state.extras = []
    if "reset_count" not in st.session_state: st.session_state.reset_count = 0

    menu = ["📝 Cargar Pedido", "📊 Pedido General", "📜 Historial", "👥 Usuarios", "📦 Catálogo"] if info["rol"] == "admin" else ["📝 Cargar", "📜 Historial"]
    tabs = st.tabs(menu)

    # --- TAB 0: CARGAR PEDIDO ---
    with tabs[0]:
        # Encabezados de Tabla (nuevo formato)
        h1, h2, h3 = st.columns([4, 2, 2])
        h1.markdown('<div class="tabla-header">Producto</div>', unsafe_allow_html=True)
        h2.markdown('<div class="tabla-header">Unidad</div>', unsafe_allow_html=True)
        h3.markdown('<div class="tabla-header">Cant.</div>', unsafe_allow_html=True)

        # Mostrar cada producto con SelectBox (centro) y TextInput (derecha)
        for prod in lista_prod_nombres:
            col_prod, col_unidad, col_cant = st.columns([4, 2, 2])
            with col_prod:
                st.write(f"**{prod}**")

            # Unidad - centro
            key_u = f"un_{prod}_{st.session_state.reset_count}"
            selected = st.session_state.unidades_sel.get(prod, "cajon/es")
            with col_unidad:
                st.session_state.unidades_sel[prod] = st.selectbox(
                    f"u_{prod}", ["cajon/es", "bolsa/s", "unidad/es"],
                    index=["cajon/es", "bolsa/s", "unidad/es"].index(selected),
                    key=key_u, label_visibility="collapsed"
                )

            # Cantidad - derecha (acepta coma, normaliza a .0 o .5)
            key_c = f"in_{prod}_{st.session_state.reset_count}"
            prev = st.session_state.cantidades.get(prod, "")
            with col_cant:
                val = st.text_input(
                    f"c_{prod}", value=prev, key=key_c, label_visibility="collapsed",
                    placeholder="0 ó 0,5"
                )
                # Validar y guardar en session_state en formato amigable (coma)
                validated = validar_cantidad(val)
                if validated == 0.0:
                    # si el usuario dejó vacío o 0, guardamos vacío para no mostrar 0 constante
                    st.session_state.cantidades[prod] = "" if str(val).strip() in ["", "0", "0,0", "0.0"] else (f"{int(validated)}" if validated.is_integer() else f"{validated:.1f}".replace('.', ','))
                else:
                    if validated.is_integer():
                        st.session_state.cantidades[prod] = f"{int(validated)}"
                    else:
                        st.session_state.cantidades[prod] = f"{validated:.1f}".replace('.', ',')

        # PRODUCTOS ADICIONALES (VISIBLE PARA TODOS)
        st.divider()
        st.write("✨ **Productos Adicionales**")
        for i, extra in enumerate(st.session_state.extras):
            ce1, ce2, ce3 = st.columns([4, 3, 3])
            with ce1: st.session_state.extras[i]['nombre'] = st.text_input(f"E_N_{i}", value=extra['nombre'], key=f"ex_n_{i}", label_visibility="collapsed", placeholder="Nombre")
            with ce2: st.session_state.extras[i]['cantidad'] = st.text_input(f"E_C_{i}", value=str(extra['cantidad']), key=f"ex_c_{i}", label_visibility="collapsed", placeholder="0")
            with ce3: st.session_state.extras[i]['unidad/es'] = st.selectbox(f"E_U_{i}", ["cajon/es", "bolsa/s", "unidad/es"], index=0, key=f"ex_u_{i}", label_visibility="collapsed")
        
        if st.button("➕ Añadir producto adicional"):
            st.session_state.extras.append({'nombre': '', 'cantidad': '', 'unidad/es': 'cajon/es'})
            st.rerun()
        
        st.divider()
        if st.button("🚀 ENVIAR PEDIDO", type="primary", use_container_width=True):
            if guardar_pedido(info["id"], st.session_state.cantidades, st.session_state.unidades_sel, st.session_state.extras):
                st.success("¡Pedido registrado!")
                time.sleep(1)
                st.rerun()
            else:
                st.warning("No hay productos con cantidad válida mayor a 0")

    # --- VISTAS DE ADMINISTRADOR ---
    if info["rol"] == "admin":
        with tabs[1]:
            res = supabase.table("pedidos").select("id, producto, cantidad, unidad_medida, usuarios(nombre_sucursal)").eq("estado", "pendiente").execute()
            if res.data:
                df_raw = pd.json_normalize(res.data)
                df_res = df_raw.groupby(['producto', 'unidad_medida'])['cantidad'].sum().reset_index()
                df_res = df_res.merge(df_maestro, left_on='producto', right_on='nombre', how='left').sort_values('orden')
                df_res_final = df_res[['producto', 'unidad_medida', 'cantidad']].rename(columns={'producto': 'Producto', 'unidad_medida': 'Unidad', 'cantidad': 'Total'})
                
                st.dataframe(df_res_final.style.format({"Total": "{:.1f}"}), use_container_width=True, hide_index=True)
                
                c_p1, c_p2 = st.columns(2)
                with c_p1:
                    pdf_compra = generar_pdf("LISTA DE COMPRA", df_res_final)
                    st.download_button("📄 PDF Compra", data=pdf_compra, file_name=f"compra_{datetime.now().strftime('%d_%m')}.pdf", type="primary", use_container_width=True)
                with c_p2:
                    pdf_envio = generar_pdf_detallado("DETALLE DE REPARTO", df_raw)
                    st.download_button("🚚 PDF Reparto", data=pdf_envio, file_name=f"reparto_{datetime.now().strftime('%d_%m')}.pdf", type="primary", use_container_width=True)
                
                st.divider()
                if st.button("✅ FINALIZAR Y LIMPIAR DÍA", type="primary", use_container_width=True):
                    for pid in df_raw['id']: 
                        supabase.table("pedidos").update({"estado": "completado"}).eq("id", pid).execute()
                    st.success("Limpieza completada")
                    st.rerun()
            else: st.info("No hay pedidos pendientes.")

        with tabs[3]:
            st.subheader("Gestión de Usuarios")
            with st.expander("➕ Nueva Sucursal"):
                with st.form("ns"):
                    nu, np, ns = st.text_input("Usuario"), st.text_input("Clave"), st.text_input("Nombre Sucursal")
                    if st.form_submit_button("Crear Cuenta", type="primary"):
                        supabase.table("usuarios").insert({"username": nu, "password": np, "nombre_sucursal": ns, "rol": "sucursal"}).execute()
                        st.rerun()
            
            res_u = supabase.table("usuarios").select("*").execute()
            for user in res_u.data:
                c1, c2, c3 = st.columns([6, 2, 2])
                with c1: st.write(f"**{user['nombre_sucursal']}** (`{user['username']}`)")
                with c2:
                    if st.button("Editar usuario", key=f"ed_u_{user['id']}", type="primary"): st.session_state[f"edit_u_{user['id']}"] = True
                with c3:
                    if user['rol'] != 'admin' and st.button("Eliminar", key=f"del_u_{user['id']}", type="primary"):
                        supabase.table("usuarios").delete().eq("id", user['id']).execute()
                        st.rerun()
                
                if st.session_state.get(f"edit_u_{user['id']}", False):
                    with st.form(f"f_ed_u_{user['id']}"):
                        ed_u = st.text_input("Login", value=user['username'])
                        ed_p = st.text_input("Clave", value=user['password'])
                        ed_s = st.text_input("Nombre", value=user['nombre_sucursal'])
                        if st.form_submit_button("Guardar", type="primary"):
                            supabase.table("usuarios").update({"username": ed_u, "password": ed_p, "nombre_sucursal": ed_s}).eq("id", user['id']).execute()
                            del st.session_state[f"edit_u_{user['id']}"]
                            st.rerun()

        with tabs[4]:
            st.subheader("Catálogo de Productos")
            with st.form("np"):
                n_p = st.text_input("Nombre de nuevo producto")
                if st.form_submit_button("Añadir al Catálogo", type="primary"):
                    if n_p:
                        supabase.table("productos_lista").insert({"nombre": n_p.strip().capitalize(), "orden": len(df_maestro)}).execute()
                        st.cache_data.clear(); st.rerun()
            
            st.divider()
            for i, row in df_maestro.iterrows():
                col1, col2, col3, col4 = st.columns([5, 1.5, 1.5, 2])
                with col1: st.write(f"**{row['nombre']}**")
                with col2:
                    if st.button("🔼", key=f"up_{row['id']}"): 
                        reordenar_producto(row['id'], row['orden'], "up", df_maestro)
                        st.rerun()
                with col3:
                    if st.button("🔽", key=f"down_{row['id']}"): 
                        reordenar_producto(row['id'], row['orden'], "down", df_maestro)
                        st.rerun()
                with col4:
                    if st.button("Borrar", key=f"x_{row['id']}", type="primary"):
                        supabase.table("productos_lista").delete().eq("id", row['id']).execute()
                        st.cache_data.clear(); st.rerun()

    # --- HISTORIAL (PARA TODOS) ---
    hist_idx = 2 if info["rol"] == "admin" else 1
    with tabs[hist_idx]:
        st.subheader("📜 Historial de Pedidos")
        query = supabase.table("pedidos").select("fecha_pedido, producto, cantidad, unidad_medida, usuarios(nombre_sucursal)")
        if info["rol"] != "admin":
            query = query.eq("usuario_id", info["id"])
        
        hist = query.order("fecha_pedido", desc=True).limit(200).execute()
        
        if hist.data:
            df_h = pd.json_normalize(hist.data)
            df_h['fecha_dt'] = pd.to_datetime(df_h['fecha_pedido'])
            def calc_sem(f):
                l = f - timedelta(days=f.weekday()); d = l + timedelta(days=6)
                return f"Semana {l.strftime('%d/%m')} al {d.strftime('%d/%m')}"
            
            df_h['Rango'] = df_h['fecha_dt'].apply(calc_sem)
            for rango in df_h['Rango'].unique():
                with st.expander(f"📅 {rango}"):
                    df_s = df_h[df_h['Rango'] == rango].copy()
                    if info["rol"] == "admin":
                        st.dataframe(df_s.groupby(['usuarios.nombre_sucursal', 'producto', 'unidad_medida'])['cantidad'].sum().reset_index(), hide_index=True)
                    else:
                        st.dataframe(df_s[['producto', 'cantidad', 'unidad_medida']], hide_index=True)
        else: st.info("No hay historial registrado.")
