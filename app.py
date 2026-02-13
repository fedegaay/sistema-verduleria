import streamlit as st
from supabase import create_client, Client
import pandas as pd

# --- CONFIGURACIÓN DE CONEXIÓN ---
URL = "https://opbgobnjqvevlvvvyweu.supabase.co"
KEY = "sb_publishable_ievWhIYrfJMnN-AXe_oz5g_lU9tujnC"
supabase: Client = create_client(URL, KEY)

# --- FUNCIONES DE LÓGICA ---
def obtener_productos():
    res = supabase.table("productos_lista").select("nombre").order("orden").execute()
    return [item['nombre'] for item in res.data]

def obtener_pedidos_propios(usuario_id):
    res = supabase.table("pedidos").select("id, producto, cantidad").eq("usuario_id", usuario_id).eq("estado", "pendiente").execute()
    return pd.DataFrame(res.data)

def upsert_pedido(usuario_id, producto, cantidad):
    """Suma cantidad si el producto existe, sino lo crea."""
    # Buscamos si ya existe el producto pendiente para este usuario
    existente = supabase.table("pedidos").select("id, cantidad").eq("usuario_id", usuario_id).eq("producto", producto).eq("estado", "pendiente").execute()
    
    if existente.data:
        nueva_cantidad = existente.data[0]['cantidad'] + cantidad
        supabase.table("pedidos").update({"cantidad": int(nueva_cantidad)}).eq("id", existente.data[0]['id']).execute()
    else:
        supabase.table("pedidos").insert({"usuario_id": usuario_id, "producto": producto, "cantidad": int(cantidad)}).execute()

# --- INTERFAZ ---
if "user_info" not in st.session_state:
    st.set_page_config(page_title="Login Verdulería", layout="centered")
    st.title("🥬 Gestión de Verdulerías")
    with st.form("login_form"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Ingresar"):
            res = supabase.table("usuarios").select("*").eq("username", u).eq("password", p).execute()
            if res.data:
                st.session_state["user_info"] = res.data[0]
                st.rerun()
            else:
                st.error("Credenciales incorrectas")

else:
    info = st.session_state["user_info"]
    st.sidebar.title(f"Hola, {info['nombre_sucursal']}")
    if st.sidebar.button("Cerrar Sesión"):
        del st.session_state["user_info"]
        st.rerun()

    lista_productos = obtener_productos()

    if info["rol"] == "admin":
        tab_carga, tab_general = st.tabs(["📝 Mi Pedido", "📋 Pedido Global"])
    else:
        tab_carga = st.container()

    # --- SECCIÓN: CARGA Y EDICIÓN ---
    with tab_carga:
        st.subheader("Cargar nuevo producto")
        with st.form("nuevo_item", clear_on_submit=True):
            p_nom = st.selectbox("Producto", lista_productos)
            p_cant = st.number_input("Cantidad de Cajones", min_value=1, step=1)
            if st.form_submit_button("Agregar"):
                upsert_pedido(info["id"], p_nom, p_cant)
                st.toast(f"Actualizado: {p_nom}")
                st.rerun()

        st.divider()
        st.subheader("Mis productos cargados")
        df_propios = obtener_pedidos_propios(info["id"])
        
        if not df_propios.empty:
            # Usamos el data_editor para permitir borrar y editar en una sola tabla
            # num_rows="dynamic" permite al usuario borrar filas seleccionándolas y pulsando 'Delete' o el icono de papelera
            edited_df = st.data_editor(
                df_propios, 
                column_order=("producto", "cantidad"), 
                hide_index=True, 
                num_rows="dynamic",
                key="editor_propios",
                use_container_width=True
            )
            
            if st.button("💾 HACER PEDIDO", type="primary"):
                # 1. Identificar filas borradas
                ids_actuales = set(edited_df["id"].tolist()) if not edited_df.empty else set()
                ids_originales = set(df_propios["id"].tolist())
                ids_a_eliminar = ids_originales - ids_actuales
                
                for id_del in ids_a_eliminar:
                    supabase.table("pedidos").delete().eq("id", id_del).execute()
                
                # 2. Actualizar cambios en productos o cantidades
                if not edited_df.empty:
                    for _, row in edited_df.iterrows():
                        supabase.table("pedidos").update({
                            "producto": row['producto'], 
                            "cantidad": int(row['cantidad'])
                        }).eq("id", row['id']).execute()
                
                st.success("✅ ¡Pedido procesado correctamente!")
                st.rerun()
        else:
            st.info("No hay productos en tu lista.")

    # --- SECCIÓN: VISTA GLOBAL (Solo Admin) ---
    if info["rol"] == "admin":
        with tab_general:
            st.subheader("Lista para el Mercado")
            res_gen = supabase.table("pedidos").select("producto, cantidad").eq("estado", "pendiente").execute()
            
            if res_gen.data:
                df_gen = pd.DataFrame(res_gen.data)
                consolidado = df_gen.groupby("producto")["cantidad"].sum().reset_index()
                
                # Ordenamiento según la base de datos
                consolidado['producto'] = pd.Categorical(consolidado['producto'], categories=lista_productos, ordered=True)
                consolidado = consolidado.sort_values('producto')
                
                st.table(consolidado.rename(columns={"producto": "Producto", "cantidad": "Cajones"}))
                
                if st.button("🏁 Finalizar Compra"):
                    supabase.table("pedidos").update({"estado": "completado"}).eq("estado", "pendiente").execute()
                    st.success("Compra archivada.")
                    st.rerun()