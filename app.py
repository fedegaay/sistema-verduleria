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
        pdf.set_font("Arial", "", 12)
        for _, row in datos.iterrows():
            pdf.cell(90, 10, str(row['Producto']), 1)
            pdf.cell(40, 10, str(row['Total']), 1)
            pdf.cell(60, 10, str(row['Unidad']), 1, ln=True)
    else:
        for suc in datos['usuarios.nombre_sucursal'].unique():
            pdf.set_font("Arial", "B", 14)
            pdf.cell(190, 10, f"Destino: {suc}", ln=True)
            df_suc = datos[datos['usuarios.nombre_sucursal'] == suc]
            for _, row in df_suc.iterrows():
                pdf.cell(130, 8, f"{row['producto']}", 1)
                pdf.cell(60, 8, f"{row['cantidad']} {row['unidad_medida']}", 1, ln=True)
            pdf.ln(5)
    return pdf.output(dest='S').encode('latin-1')

# --- FUNCIONES DE BASE DE DATOS ---
@st.cache_data
def obtener_productos():
    res = supabase.table("productos_lista").select("nombre").order("orden").execute()
    return [item['nombre'] for item in res.data]

def guardar_pedido(usuario_id, dict_pedidos, dict_unidades, lista_extras):
    # Guardar productos de la lista fija
    for prod, cant in dict_pedidos.items():
        if cant > 0:
            supabase.table("pedidos").insert({
                "usuario_id": usuario_id, "producto": prod, 
                "cantidad": float(cant), "unidad_medida": dict_unidades[prod],
                "estado": "pendiente"
            }).execute()
    
    # Guardar productos extra dinámicos
    for extra in lista_extras:
        if extra['nombre'] and extra['cantidad'] > 0:
            supabase.table("pedidos").insert({
                "usuario_id": usuario_id, "producto": extra['nombre'].strip().capitalize(),
                "cantidad": float(extra['cantidad']), "unidad_medida": extra['unidad'],
                "estado": "pendiente"
            }).execute()
    
    # Reset
    st.session_state.cantidades = {p: 0.0 for p in dict_pedidos}
    st.session_state.extras = [] # Limpiar extras
    st.session_state.reset_count = st.session_state.get('reset_count', 0) + 1

# --- LOGIN ---
if "user_info" not in st.session_state:
    st.title("🥬 Gestión de Verdulerías")
    with st.form("login"):
        u = st.text_input("Usuario")
        p = st.text_input("Clave", type="password")
        if st.form_submit_button("Entrar"):
            res = supabase.table("usuarios").select("*").eq("username", u).eq("password", p).execute()
            if res.data:
                st.session_state["user_info"] = res.data[0]
                st.rerun()
            else: st.error("Acceso denegado")

else:
    info = st.session_state["user_info"]
    
    # Encabezado
    col_suc, col_out = st.columns([0.7, 0.3])
    with col_suc: st.subheader(f"📍 {info['nombre_sucursal']}")
    with col_out:
        if st.button("Cerrar Sesión", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    st.divider()
    lista_prod = obtener_productos()
    
    if "cantidades" not in st.session_state:
        st.session_state.cantidades = {p: 0.0 for p in lista_prod}
    if "unidades_sel" not in st.session_state:
        st.session_state.unidades_sel = {p: "cajon" for p in lista_prod}
    if "extras" not in st.session_state:
        st.session_state.extras = []
    if "reset_count" not in st.session_state:
        st.session_state.reset_count = 0

    tabs = st.tabs(["📝 Cargar", "📊 Consolidado", "📜 Historial"] if info["rol"] == "admin" else ["📝 Cargar", "📜 Historial"])

    with tabs[0]:
        # Lista fija
        for prod in lista_prod:
            c1, c2, c3 = st.columns([3.5, 3.5, 3])
            with c1: st.write(f"**{prod}**")
            with c2:
                val = st.number_input("n", label_visibility="collapsed", min_value=0.0, step=0.5, 
                                    value=float(st.session_state.cantidades[prod]), 
                                    key=f"in_{prod}_{st.session_state.reset_count}")
                st.session_state.cantidades[prod] = val
            with c3:
                opcion = st.selectbox("u", ["cajon", "unidad"], key=f"un_{prod}_{st.session_state.reset_count}", label_visibility="collapsed")
                st.session_state.unidades_sel[prod] = opcion

        # SECCIÓN DE EXTRAS DINÁMICOS (SOLO ADMIN)
        if info["rol"] == "admin":
            st.divider()
            st.write("✨ **Compras de Oportunidad**")
            
            # Renderizar filas extras que ya existen
            for i, extra in enumerate(st.session_state.extras):
                ce1, ce2, ce3 = st.columns([4, 3, 3])
                with ce1:
                    st.session_state.extras[i]['nombre'] = st.text_input(f"Prod {i}", value=extra['nombre'], key=f"ex_n_{i}", label_visibility="collapsed", placeholder="Nombre")
                with ce2:
                    st.session_state.extras[i]['cantidad'] = st.number_input(f"Cant {i}", value=extra['cantidad'], min_value=0.0, step=0.5, key=f"ex_c_{i}", label_visibility="collapsed")
                with ce3:
                    st.session_state.extras[i]['unidad'] = st.selectbox(f"Un {i}", ["cajon", "unidad"], index=0 if extra['unidad']=="cajon" else 1, key=f"ex_u_{i}", label_visibility="collapsed")
            
            # Botón para añadir una nueva fila
            if st.button("➕ Añadir otro producto"):
                st.session_state.extras.append({'nombre': '', 'cantidad': 0.0, 'unidad': 'cajon'})
                st.rerun()

        st.divider()
        if st.button("🚀 ENVIAR PEDIDO COMPLETO", type="primary", use_container_width=True):
            guardar_pedido(info["id"], st.session_state.cantidades, st.session_state.unidades_sel, st.session_state.extras)
            st.toast("✅ ¡Pedido y extras enviados!")
            time.sleep(1)
            st.rerun()

    # --- PESTAÑAS DE CONSOLIDADO Y HISTORIAL (Sin cambios significativos en lógica) ---
    if info["rol"] == "admin":
        with tabs[1]:
            res = supabase.table("pedidos").select("id, producto, cantidad, unidad_medida, usuarios(nombre_sucursal)").eq("estado", "pendiente").execute()
            if res.data:
                df_p = pd.json_normalize(res.data)
                df_res = df_p.groupby(['producto', 'unidad_medida'])['cantidad'].sum().reset_index()
                df_res.columns = ['Producto', 'Unidad', 'Total']
                st.table(df_res)
                
                c_p1, c_p2 = st.columns(2)
                with c_p1:
                    pdf_c = generar_pdf("LISTA DE COMPRA", df_res)
                    st.download_button("📄 PDF Compra", data=pdf_c, file_name="compra.pdf")
                with c_p2:
                    if st.button("✅ COMPRA REALIZADA", type="primary", use_container_width=True):
                        for pid in df_p['id']:
                            supabase.table("pedidos").update({"estado": "completado"}).eq("id", pid).execute()
                        st.success("¡Compra finalizada!")
                        st.rerun()
            else: st.info("Nada pendiente.")

    with tabs[-1]:
        query = supabase.table("pedidos").select("fecha_pedido, producto, cantidad, unidad_medida, usuarios(nombre_sucursal)")
        if info["rol"] != "admin": query = query.eq("usuario_id", info["id"])
        hist = query.order("created_at", desc=True).limit(200).execute()
        if hist.data:
            df_h = pd.json_normalize(hist.data)
            df_h['fecha_dt'] = pd.to_datetime(df_h['fecha_pedido'])
            def calc_sem(f):
                l = f - timedelta(days=f.weekday()); d = l + timedelta(days=6)
                return f"Semana del {l.strftime('%d/%m/%y')} al {d.strftime('%d/%m/%y')}"
            df_h['Rango'] = df_h['fecha_dt'].apply(calc_sem)
            for rango in df_h['Rango'].unique():
                with st.expander(f"📅 {rango}"):
                    df_s = df_h[df_h['Rango'] == rango]
                    st.dataframe(df_s[['usuarios.nombre_sucursal', 'producto', 'cantidad', 'unidad_medida']], use_container_width=True, hide_index=True)