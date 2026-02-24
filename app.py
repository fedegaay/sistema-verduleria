import streamlit as st
from supabase import create_client, Client
import pandas as pd
import time
from datetime import timedelta, datetime
from fpdf import FPDF

# --- CONFIGURACIÓN DE CONEXIÓN ---
URL = "https://gosjojpueocxpyiqhvfr.supabase.co"
KEY = "sb_publishable_rZUwiJl548Ii1CwaJ87wLw_MA3oJzjT"
supabase: Client = create_client(URL, KEY)

# --- ELIMINAR ANCLAS DE LOS TÍTULOS ---
st.markdown("""
    <style>
    /* Oculta el ícono de cadena/link al lado de los títulos */
    .stToolbarActionButton {
        display: none;
    }

    ._profilePreview_gzau3_63 {
        display: none;
    }
    
    
    /* Específicamente para los headers de Streamlit */
    button[data-baseweb="tab"] > div > span > a, 
    h1 a, h2 a, h3 a, h4 a, h5 a, h6 a {
        display: none !important;
    }
    /* Quita el subrayado y efecto hover que genera el link */
    h1:hover a, h2:hover a, h3:hover a, h4:hover a, h5:hover a, h6:hover a {
        visibility: hidden !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- LÓGICA DE PERSISTENCIA DE SESIÓN ---
def check_session():
    if "user_id" in st.query_params and "user_info" not in st.session_state:
        u_id = st.query_params["user_id"]
        res = supabase.table("usuarios").select("*").eq("id", u_id).execute()
        if res.data:
            st.session_state["user_info"] = res.data[0]

# --- FUNCIÓN PARA GENERAR PDF ---
def generar_pdf(titulo, datos, es_detallado=False):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(190, 10, titulo, ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("Arial", "B", 12)
    if not es_detallado:
        pdf.cell(90, 10, "Producto", 1)
        pdf.cell(40, 10, "Cant.", 1)
        pdf.cell(60, 10, "Unidad", 1, ln=True)
        pdf.set_font("Arial", "", 10)
        for _, row in datos.iterrows():
            pdf.cell(90, 10, str(row['Producto']), 1)
            pdf.cell(40, 10, f"{float(row['Total']):.1f}", 1)
            pdf.cell(60, 10, str(row['Unidad']), 1, ln=True)
    return pdf.output(dest='S').encode('latin-1')

# --- FUNCIONES DE MAESTRO DE PRODUCTOS ---
def obtener_maestro_productos():
    res = supabase.table("productos_lista").select("nombre, orden, id").order("orden").execute()
    return pd.DataFrame(res.data)

def reordenar_producto(prod_id, orden_actual, direccion, df_completo):
    if direccion == "up" and orden_actual > 0:
        target_index = orden_actual - 1
    elif direccion == "down" and orden_actual < len(df_completo) - 1:
        target_index = orden_actual + 1
    else:
        return
    idx_target = df_completo.index[df_completo['orden'] == target_index][0]
    target_id = df_completo.iloc[idx_target]['id']
    supabase.table("productos_lista").update({"orden": target_index}).eq("id", prod_id).execute()
    supabase.table("productos_lista").update({"orden": orden_actual}).eq("id", target_id).execute()
    st.cache_data.clear()

def guardar_pedido(usuario_id, dict_pedidos, dict_unidades, lista_extras):
    for prod, cant in dict_pedidos.items():
        if cant > 0:
            supabase.table("pedidos").insert({
                "usuario_id": usuario_id, "producto": prod, 
                "cantidad": round(float(cant), 1), "unidad_medida": dict_unidades[prod],
                "estado": "pendiente"
            }).execute()
    for extra in lista_extras:
        if extra['nombre'] and extra['cantidad'] > 0:
            supabase.table("pedidos").insert({
                "usuario_id": usuario_id, "producto": extra['nombre'].strip().capitalize(),
                "cantidad": round(float(extra['cantidad']), 1), "unidad_medida": extra['unidad/es'],
                "estado": "pendiente"
            }).execute()
    st.session_state.cantidades = {}
    st.session_state.extras = [] 
    st.session_state.reset_count = st.session_state.get('reset_count', 0) + 1

# --- INICIO ---
check_session()

if "user_info" not in st.session_state:
    st.title("El Rey Verdu - Pedidos")
    with st.form("login"):
        u = st.text_input("Usuario")
        p = st.text_input("Clave", type="password")
        if st.form_submit_button("Iniciar Sesion", type="primary", use_container_width=True):
            res = supabase.table("usuarios").select("*").eq("username", u).eq("password", p).execute()
            if res.data:
                st.session_state["user_info"] = res.data[0]
                st.query_params["user_id"] = res.data[0]["id"]
                st.rerun()
            else: st.error("Acceso denegado")
else:
    info = st.session_state["user_info"]
    c_suc, c_out = st.columns([0.7, 0.3])
    with c_suc: st.subheader(f"📍 {info['nombre_sucursal']}")
    with c_out:
        if st.button("Cerrar Sesion", type="primary", use_container_width=True):
            st.session_state.clear()
            st.query_params.clear()
            st.rerun()

    df_maestro = obtener_maestro_productos()
    lista_prod_nombres = df_maestro['nombre'].tolist()
    
    if "cantidades" not in st.session_state: st.session_state.cantidades = {p: 0.0 for p in lista_prod_nombres}
    if "unidades_sel" not in st.session_state: st.session_state.unidades_sel = {p: "cajon/es" for p in lista_prod_nombres}
    if "extras" not in st.session_state: st.session_state.extras = []
    if "reset_count" not in st.session_state: st.session_state.reset_count = 0

    menu = ["📝 Cargar Pedido", "📊 Pedido General", "📜 Historial de Compras", "👥 Usuarios", "📦 Listado de Productos"] if info["rol"] == "admin" else ["📝 Cargar", "📜 Historial"]
    tabs = st.tabs(menu)

    # --- PESTAÑA 0: CARGA ---
    with tabs[0]:
        @st.fragment
        def render_items():
            for prod in lista_prod_nombres:
                c1, c2, c3 = st.columns([4, 3, 3])
                with c1: st.write(f"**{prod}**")
                with c2:
                    st.session_state.cantidades[prod] = st.number_input("n", label_visibility="collapsed", min_value=0.0, step=0.5, format="%.1f", value=float(st.session_state.cantidades.get(prod, 0.0)), key=f"in_{prod}_{st.session_state.reset_count}")
                with c3:
                    st.session_state.unidades_sel[prod] = st.selectbox("u", ["cajon/es", "unidad/es"], label_visibility="collapsed", key=f"un_{prod}_{st.session_state.reset_count}")
            
            if info["rol"] == "admin":
                st.divider()
                st.write("✨ **Productos Adicionales**")
                for i, extra in enumerate(st.session_state.extras):
                    ce1, ce2, ce3 = st.columns([4, 3, 3])
                    with ce1: st.session_state.extras[i]['nombre'] = st.text_input(f"P{i}", value=extra['nombre'], key=f"ex_n_{i}", label_visibility="collapsed", placeholder="Producto")
                    with ce2: st.session_state.extras[i]['cantidad'] = st.number_input(f"C{i}", value=float(extra['cantidad']), min_value=0.0, step=0.5, format="%.1f", key=f"ex_c_{i}", label_visibility="collapsed")
                    with ce3: st.session_state.extras[i]['unidad/es'] = st.selectbox(f"U{i}", ["cajon/es", "unidad/es"], index=0 if extra['unidad/es']=="cajon/es" else 1, key=f"ex_u_{i}", label_visibility="collapsed")
                if st.button("➕ Añadir nuevo producto"):
                    st.session_state.extras.append({'nombre': '', 'cantidad': 0.0, 'unidad/es': 'cajon/es'})
                    st.rerun()
            
            st.divider()
            if st.button("🚀 ENVIAR PEDIDO", type="primary", use_container_width=True):
                guardar_pedido(info["id"], st.session_state.cantidades, st.session_state.unidades_sel, st.session_state.extras)
                st.toast("✅ ¡Registrado!")
                time.sleep(1)
                st.rerun()
        render_items()

    # --- SOLUCIÓN AL ERROR DE PESTAÑAS ---
    if info["rol"] == "admin":
        with tabs[1]:
            res = supabase.table("pedidos").select("id, producto, cantidad, unidad_medida, usuarios(nombre_sucursal)").eq("estado", "pendiente").execute()
            if res.data:
                df_p = pd.json_normalize(res.data)
                df_res = df_p.groupby(['producto', 'unidad_medida'])['cantidad'].sum().reset_index()
                df_res = df_res.merge(df_maestro, left_on='producto', right_on='nombre', how='left').sort_values('orden')
                df_res_final = df_res[['producto', 'unidad_medida', 'cantidad']].rename(columns={'producto': 'Producto', 'unidad_medida': 'Unidad', 'cantidad': 'Total'})
                st.dataframe(df_res_final.style.format({"Total": "{:.1f}"}), use_container_width=True, hide_index=True)
                c_p1, c_p2 = st.columns(2)
                with c_p1:
                    pdf_c = generar_pdf("LISTA DE COMPRA", df_res_final)
                    st.download_button("📄 PDF Compra", data=pdf_c, file_name="compra.pdf", type="primary", use_container_width=True)
                with c_p2:
                    if st.button("✅ COMPRA FINALIZADA", type="primary", use_container_width=True):
                        for pid in df_p['id']: supabase.table("pedidos").update({"estado": "completado"}).eq("id", pid).execute()
                        st.success("¡Listo!")
                        st.rerun()
            else: st.info("No hay pedidos pendientes.")

        with tabs[2]:
            st.subheader("📜 Historial de Compras (General)")
            query = supabase.table("pedidos").select("fecha_pedido, producto, cantidad, unidad_medida, usuarios(nombre_sucursal)")
            hist = query.order("fecha_pedido", desc=True).limit(500).execute()
            if hist.data:
                df_h = pd.json_normalize(hist.data)
                df_h['fecha_dt'] = pd.to_datetime(df_h['fecha_pedido'])
                def calc_sem(f):
                    l = f - timedelta(days=f.weekday()); d = l + timedelta(days=6)
                    return f"Semana del {l.strftime('%d/%m/%y')} al {d.strftime('%d/%m/%y')}"
                df_h['Rango'] = df_h['fecha_dt'].apply(calc_sem)
                for rango in df_h['Rango'].unique():
                    with st.expander(f"📅 {rango}"):
                        df_s = df_h[df_h['Rango'] == rango].copy()
                        df_agrupado = df_s.groupby(['usuarios.nombre_sucursal', 'producto', 'unidad_medida'])['cantidad'].sum().reset_index()
                        df_agrupado = df_agrupado.merge(df_maestro, left_on='producto', right_on='nombre', how='left').sort_values(['usuarios.nombre_sucursal', 'orden'])
                        st.dataframe(df_agrupado[['usuarios.nombre_sucursal', 'producto', 'cantidad', 'unidad_medida']], hide_index=True)

        with tabs[3]:
            st.subheader("Gestión de Cuentas")
            with st.expander("➕ Agregar Nueva Sucursal"):
                with st.form("ns"):
                    nu, np, ns = st.text_input("Usuario (Login)"), st.text_input("Contraseña"), st.text_input("Nombre de la Sucursal")
                    if st.form_submit_button("Crear"):
                        supabase.table("usuarios").insert({"username": nu, "password": np, "nombre_sucursal": ns, "rol": "sucursal"}).execute()
                        st.rerun()
            st.divider()
            res_u = supabase.table("usuarios").select("*").execute()
            for user in res_u.data:
                c1, c2, c3 = st.columns([6, 2, 2])
                with c1: st.write(f"**{user['nombre_sucursal']}** ({user['username']})")
                with c2:
                    if st.button("Editar", key=f"ed_u_{user['id']}", type="primary", use_container_width=True): st.session_state[f"edit_u_{user['id']}"] = True
                with c3:
                    if user['rol'] != 'admin':
                        if st.button("Eliminar", key=f"del_u_{user['id']}", type="primary", use_container_width=True):
                            supabase.table("usuarios").delete().eq("id", user['id']).execute()
                            st.rerun()
                if st.session_state.get(f"edit_u_{user['id']}", False):
                    with st.form(f"f_ed_u_{user['id']}"):
                        ed_u = st.text_input("Login", value=user['username'])
                        ed_p = st.text_input("Clave", value=user['password'])
                        ed_s = st.text_input("Sucursal", value=user['nombre_sucursal'])
                        col_f1, col_f2 = st.columns(2)
                        with col_f1:
                            if st.form_submit_button("Guardar"):
                                supabase.table("usuarios").update({"username": ed_u, "password": ed_p, "nombre_sucursal": ed_s}).eq("id", user['id']).execute()
                                del st.session_state[f"edit_u_{user['id']}"]
                                st.rerun()
                        with col_f2:
                            if st.form_submit_button("Cancelar"):
                                del st.session_state[f"edit_u_{user['id']}"]
                                st.rerun()

        with tabs[4]:
            st.subheader("Catálogo")
            with st.form("np"):
                n_p = st.text_input("Nombre de nueva fruta/verdura")
                if st.form_submit_button("Agregar producto"):
                    if n_p:
                        supabase.table("productos_lista").insert({"nombre": n_p.strip().capitalize(), "orden": len(df_maestro)}).execute()
                        st.cache_data.clear(); st.rerun()
            st.divider()
            for i, row in df_maestro.iterrows():
                col1, col2, col3, col4 = st.columns([5, 1.5, 1.5, 2])
                with col1: st.write(f"**{row['nombre']}**")
                with col2:
                    if st.button("🔼", key=f"up_{row['id']}"): reordenar_producto(row['id'], row['orden'], "up", df_maestro); st.rerun()
                with col3:
                    if st.button("🔽", key=f"down_{row['id']}"): reordenar_producto(row['id'], row['orden'], "down", df_maestro); st.rerun()
                with col4:
                    if st.button("Eliminar", key=f"x_{row['id']}", type="primary", use_container_width=True):
                        supabase.table("productos_lista").delete().eq("id", row['id']).execute()
                        st.cache_data.clear(); st.rerun()
    else:
        # Aquí el historial para la Sucursal (es su segunda pestaña, índice 1)
        with tabs[1]:
            st.subheader("📜 Mi Historial de Pedidos")
            query = supabase.table("pedidos").select("fecha_pedido, producto, cantidad, unidad_medida, usuarios(nombre_sucursal)")
            hist = query.eq("usuario_id", info["id"]).order("fecha_pedido", desc=True).limit(500).execute()
            if hist.data:
                df_h = pd.json_normalize(hist.data)
                df_h['fecha_dt'] = pd.to_datetime(df_h['fecha_pedido'])
                def calc_sem(f):
                    l = f - timedelta(days=f.weekday()); d = l + timedelta(days=6)
                    return f"Semana del {l.strftime('%d/%m/%y')} al {d.strftime('%d/%m/%y')}"
                df_h['Rango'] = df_h['fecha_dt'].apply(calc_sem)
                for rango in df_h['Rango'].unique():
                    with st.expander(f"📅 {rango}"):
                        df_s = df_h[df_h['Rango'] == rango].copy()
                        st.dataframe(df_s[['producto', 'cantidad', 'unidad_medida']], hide_index=True)
            else:
                st.info("Aún no has realizado pedidos.")




