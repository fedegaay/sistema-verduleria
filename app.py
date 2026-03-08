import streamlit as st
from supabase import create_client, Client
import pandas as pd
import time
from datetime import timedelta, datetime
from fpdf import FPDF
import unicodedata
import hashlib

# ─────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(URL, KEY)

st.set_page_config(page_title="El Rey Verdu", layout="centered")

st.markdown("""
<style>
/* Ocultar decoraciones */
.stToolbarActionButton { display: none !important; }
h1 a, h2 a, h3 a, h4 a { display: none !important; }
[data-testid="stHeader"] { background: transparent !important; }
footer { display: none !important; }

/* Reducir padding general de la página */
[data-testid="stAppViewContainer"] > section > div {
    padding-top: 0.5rem !important;
}
.block-container {
    padding-top: 0.5rem !important;
    padding-bottom: 1rem !important;
}

/* Columnas: nunca apilar, siempre en línea */
[data-testid="stHorizontalBlock"] {
    flex-wrap: nowrap !important;
    align-items: center !important;
    gap: 3px !important;
}
[data-testid="column"] {
    min-width: 0 !important;
    padding: 0 2px !important;
}

/* Botones pequeños y compactos siempre */
.stButton > button {
    padding: 4px 6px !important;
    font-size: 12px !important;
    line-height: 1.3 !important;
    min-height: 0 !important;
    white-space: nowrap !important;
}

/* Tabs más compactos */
.stTabs [data-baseweb="tab"] {
    padding: 6px 8px !important;
    font-size: 12px !important;
}

/* Reducir espacio entre elementos */
.stMarkdown { margin-bottom: 0 !important; }
[data-testid="stVerticalBlock"] > div { gap: 0.3rem !important; }

/* Cabecera verde de tablas */
.tbl-header {
    display: flex;
    background: #2e7d32;
    color: white;
    border-radius: 6px;
    padding: 6px 6px;
    font-weight: 700;
    font-size: 12px;
    margin-bottom: 2px;
    gap: 3px;
    align-items: center;
}
.th       { text-align: center; flex-shrink: 0; }
.th-left  { text-align: left; }

/* Separador de filas */
.row-sep { border: none; border-top: 1px solid #eee; margin: 1px 0; }

/* Nombre en filas */
.nombre-txt {
    font-size: 13px; font-weight: 600;
    padding-top: 3px; line-height: 1.3;
    word-break: break-word;
}
.sub-txt { font-size: 11px; color: #888; line-height: 1.2; }

/* Header sucursal compacto */
.suc-header {
    background: #f1f8e9;
    border-left: 4px solid #2e7d32;
    border-radius: 6px;
    padding: 8px 12px;
    margin-bottom: 6px;
}
.suc-nombre { font-size: 15px; font-weight: 700; color: #1b5e20; margin: 0; }
.suc-salir  {
    font-size: 12px; color: #888; cursor: pointer;
    margin-top: 2px; display: inline-block;
    background: none; border: none; padding: 0;
    text-decoration: underline;
}
</style>
""", unsafe_allow_html=True)

UNIDADES = ["cajon/es", "bolsa/s", "unidad/es"]

# ─────────────────────────────────────────────
# SOPORTE
# ─────────────────────────────────────────────

def normalizar_texto(texto):
    if not texto:
        return ""
    return "".join(
        c for c in unicodedata.normalize('NFKD', str(texto))
        if unicodedata.category(c) != 'Mn'
    )

def hashear_password(p: str) -> str:
    return hashlib.sha256(p.encode()).hexdigest()

def validar_cantidad(valor):
    try:
        if valor is None or str(valor).strip() == "":
            return 0.0
        num = float(str(valor).replace(',', '.'))
        return round(num * 2) / 2
    except Exception:
        return 0.0

@st.cache_data(ttl=60)
def obtener_maestro_productos():
    res = supabase.table("productos_lista").select("nombre, orden, id").order("orden").execute()
    return pd.DataFrame(res.data)

def check_session():
    if "user_info" in st.session_state:
        return
    u_id = st.query_params.get("uid", "")
    if u_id and len(u_id) == 36:
        try:
            res = supabase.table("usuarios").select("*").eq("id", u_id).execute()
            if res.data:
                st.session_state["user_info"] = res.data[0]
        except Exception:
            pass

# ─────────────────────────────────────────────
# PDFs
# ─────────────────────────────────────────────

def generar_pdf(titulo, datos):
    pdf = FPDF(); pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(190, 10, normalizar_texto(titulo), ln=True, align="C"); pdf.ln(10)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(90, 14, "Producto", 1); pdf.cell(40, 14, "Cant.", 1); pdf.cell(60, 14, "Unidad", 1, ln=True)
    pdf.set_font("Arial", "", 12)
    for _, r in datos.iterrows():
        pdf.cell(90, 14, normalizar_texto(r['Producto']), 1)
        pdf.cell(40, 14, f"{float(r['Total']):.1f}", 1)
        pdf.cell(60, 14, normalizar_texto(r['Unidad']), 1, ln=True)
    return bytes(pdf.output())

def generar_pdf_detallado(titulo, df_raw):
    pdf = FPDF(); pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(190, 10, normalizar_texto(titulo), ln=True, align="C"); pdf.ln(10)
    col_suc = 'usuarios.nombre_sucursal'
    if col_suc in df_raw.columns:
        for s in df_raw[col_suc].dropna().unique():
            pdf.set_font("Arial", "B", 14); pdf.set_fill_color(240, 240, 240)
            pdf.cell(190, 12, f"SUCURSAL: {normalizar_texto(str(s))}", 1, ln=True, fill=True)
            pdf.set_font("Arial", "B", 10)
            pdf.cell(100, 14, "Producto", 1); pdf.cell(45, 14, "Cantidad", 1); pdf.cell(45, 14, "Unidad", 1, ln=True)
            pdf.set_font("Arial", "", 11)
            for _, r in df_raw[df_raw[col_suc] == s].iterrows():
                pdf.cell(100, 14, normalizar_texto(str(r.get('producto', ''))), 1)
                pdf.cell(45, 14, f"{float(r.get('cantidad', 0)):.1f}", 1)
                pdf.cell(45, 14, normalizar_texto(str(r.get('unidad_medida', ''))), 1, ln=True)
            pdf.ln(10)
    return bytes(pdf.output())

# ─────────────────────────────────────────────
# GUARDAR PEDIDO
# ─────────────────────────────────────────────

def guardar_pedido(usuario_id, df_editor, extras):
    batch = []
    for _, row in df_editor.iterrows():
        cant = validar_cantidad(row.get('Cantidad', 0))
        if cant > 0:
            batch.append({
                "usuario_id":    usuario_id,
                "producto":      str(row['Producto']),
                "cantidad":      cant,
                "unidad_medida": str(row['Unidad']),
                "estado":        "pendiente"
            })
    for ex in extras:
        cant   = validar_cantidad(ex.get('cant', 0))
        nombre = str(ex.get('nombre', '')).strip()
        if nombre and cant > 0:
            batch.append({
                "usuario_id":    usuario_id,
                "producto":      nombre,
                "cantidad":      cant,
                "unidad_medida": ex.get('unidad', 'cajon/es'),
                "estado":        "pendiente"
            })
    if batch:
        supabase.table("pedidos").insert(batch).execute()
        return True
    return False

# ─────────────────────────────────────────────
# REORDENAR
# ─────────────────────────────────────────────

def reordenar(pid, orden_actual, direccion, df):
    target = orden_actual - 1 if direccion == "up" else orden_actual + 1
    if target < 0 or target >= len(df):
        return
    vecino = supabase.table("productos_lista").select("id").eq("orden", target).execute()
    if vecino.data:
        vid = vecino.data[0]['id']
        supabase.table("productos_lista").update({"orden": target}).eq("id", pid).execute()
        supabase.table("productos_lista").update({"orden": orden_actual}).eq("id", vid).execute()
        st.cache_data.clear()

# ─────────────────────────────────────────────
# RENDER: PEDIDO
# ─────────────────────────────────────────────

def render_pedido(usuario_id, lista_productos):
    if "extras" not in st.session_state:
        st.session_state.extras = []

    df_base = pd.DataFrame({
        "Producto": lista_productos,
        "Cantidad": [0.0] * len(lista_productos),
        "Unidad":   [UNIDADES[0]] * len(lista_productos),
    })

    st.caption("Completá la cantidad. Dejá en 0 lo que no pedís.")
    df_edit = st.data_editor(
        df_base,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={
            "Producto": st.column_config.TextColumn("Producto", disabled=True, width="medium"),
            "Cantidad": st.column_config.NumberColumn("Cant.", min_value=0, step=0.5, format="%.1f", width="small"),
            "Unidad":   st.column_config.SelectboxColumn("Unidad", options=UNIDADES, width="medium"),
        },
        key="data_editor_pedido"
    )

    st.divider()
    st.markdown("**✨ Productos adicionales**")

    extras_actuales = []
    for i, ex in enumerate(st.session_state.extras):
        c1, c2, c3, c4 = st.columns([4, 2, 3, 1], gap="small")
        with c1:
            nom = st.text_input("Producto", value=ex.get('nombre', ''),
                                key=f"ex_nom_{i}", label_visibility="collapsed",
                                placeholder="Nombre")
        with c2:
            cant = st.number_input("Cant", value=float(ex.get('cant', 0)),
                                   min_value=0.0, step=0.5,
                                   key=f"ex_cant_{i}", label_visibility="collapsed",
                                   format="%.1f")
        with c3:
            unid = st.selectbox("Unidad", UNIDADES,
                                index=UNIDADES.index(ex.get('unidad', UNIDADES[0])),
                                key=f"ex_unid_{i}", label_visibility="collapsed")
        with c4:
            if st.button("🗑️", key=f"ex_del_{i}"):
                st.session_state.extras.pop(i)
                st.rerun()
        extras_actuales.append({'nombre': nom, 'cant': cant, 'unidad': unid})
    st.session_state.extras = extras_actuales

    if st.button("➕ Agregar adicional", use_container_width=True):
        st.session_state.extras.append({'nombre': '', 'cant': 0.0, 'unidad': UNIDADES[0]})
        st.rerun()

    st.divider()
    if st.button("🚀 ENVIAR PEDIDO", type="primary", use_container_width=True):
        if guardar_pedido(usuario_id, df_edit, st.session_state.extras):
            st.session_state.extras = []
            st.success("✅ ¡Pedido registrado!")
            time.sleep(1.5)
            st.rerun()
        else:
            st.warning("⚠️ No hay cantidades mayores a 0.")

# ─────────────────────────────────────────────
# RENDER: CATÁLOGO
# ─────────────────────────────────────────────

def render_catalogo(df_maestro):
    st.markdown("""
    <div class="tbl-header">
      <div style="flex:7" class="th-left">Producto</div>
      <div style="width:32px" class="th">↑</div>
      <div style="width:32px" class="th">↓</div>
      <div style="width:40px" class="th">🗑️</div>
    </div>""", unsafe_allow_html=True)

    for _, row in df_maestro.iterrows():
        pid   = str(row['id'])
        orden = int(row['orden'])
        # Proporciones: nombre ocupa el espacio, 3 botones son fijos y angostos
        c1, c2, c3, c4 = st.columns([7, 1, 1, 1], gap="small")
        with c1:
            st.markdown(f"<div class='nombre-txt'>{row['nombre']}</div>",
                        unsafe_allow_html=True)
        with c2:
            if st.button("↑", key=f"up_{pid}", use_container_width=True):
                reordenar(pid, orden, "up", df_maestro)
                st.rerun()
        with c3:
            if st.button("↓", key=f"dn_{pid}", use_container_width=True):
                reordenar(pid, orden, "down", df_maestro)
                st.rerun()
        with c4:
            if st.button("✕", key=f"del_{pid}", use_container_width=True,
                         type="primary"):
                supabase.table("productos_lista").delete().eq("id", pid).execute()
                st.cache_data.clear()
                st.rerun()
        st.markdown("<hr class='row-sep'>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# RENDER: USUARIOS
# ─────────────────────────────────────────────

def render_usuarios(usuarios):
    st.markdown("""
    <div class="tbl-header">
      <div style="flex:6" class="th-left">Sucursal / Login</div>
      <div style="width:42px" class="th">✏️</div>
      <div style="width:42px" class="th">🗑️</div>
    </div>""", unsafe_allow_html=True)

    for user in usuarios:
        uid    = str(user['id'])
        nombre = user['nombre_sucursal']
        login  = user['username']
        es_adm = user['rol'] == 'admin'

        c1, c2, c3 = st.columns([6, 1, 1], gap="small")
        with c1:
            st.markdown(
                f"<div class='nombre-txt'>{nombre}</div>"
                f"<div class='sub-txt'>{login}</div>",
                unsafe_allow_html=True)
        with c2:
            if st.button("✏️", key=f"ed_{uid}", use_container_width=True):
                k = f"show_edit_{uid}"
                st.session_state[k] = not st.session_state.get(k, False)
                st.rerun()
        with c3:
            if not es_adm:
                if st.button("✕", key=f"du_{uid}", use_container_width=True,
                             type="primary"):
                    supabase.table("usuarios").delete().eq("id", uid).execute()
                    st.rerun()

        if st.session_state.get(f"show_edit_{uid}", False):
            with st.form(f"fedit_{uid}"):
                ed_u = st.text_input("Login",           value=login)
                ed_p = st.text_input("Nueva clave (vacío = no cambiar)", type="password")
                ed_s = st.text_input("Nombre Sucursal", value=nombre)
                ok, cancel = st.columns(2)
                with ok:
                    if st.form_submit_button("💾 Guardar", type="primary",
                                            use_container_width=True):
                        upd = {"username": ed_u.strip(), "nombre_sucursal": ed_s.strip()}
                        if ed_p.strip():
                            upd["password"] = hashear_password(ed_p)
                        supabase.table("usuarios").update(upd).eq("id", uid).execute()
                        st.session_state[f"show_edit_{uid}"] = False
                        st.success("Usuario actualizado.")
                        st.rerun()
                with cancel:
                    if st.form_submit_button("Cancelar", use_container_width=True):
                        st.session_state[f"show_edit_{uid}"] = False
                        st.rerun()

        st.markdown("<hr class='row-sep'>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# APP PRINCIPAL
# ─────────────────────────────────────────────

check_session()

# ── LOGIN ────────────────────────────────────
if "user_info" not in st.session_state:
    st.markdown("<h2 style='text-align:center;margin-bottom:16px'>📍 El Rey Verdu<br><small>Pedidos</small></h2>",
                unsafe_allow_html=True)
    with st.form("login"):
        u = st.text_input("Usuario")
        p = st.text_input("Clave", type="password")
        if st.form_submit_button("Iniciar Sesión", type="primary", use_container_width=True):
            p_hash = hashear_password(p)
            res = supabase.table("usuarios").select("*") \
                          .eq("username", u).eq("password", p_hash).execute()
            if not res.data:
                res = supabase.table("usuarios").select("*") \
                              .eq("username", u).eq("password", p).execute()
            if res.data:
                st.session_state["user_info"] = res.data[0]
                st.query_params["uid"] = res.data[0]["id"]
                st.rerun()
            else:
                st.error("Acceso denegado.")

# ── APP ──────────────────────────────────────
else:
    info     = st.session_state["user_info"]
    es_admin = info["rol"] == "admin"
    uid      = info["id"]

    # Asegurar uid en URL
    if st.query_params.get("uid", "") != uid:
        st.query_params["uid"] = uid

    # ── Header compacto: nombre arriba, botón salir abajo ──
    st.markdown(
        f"""<div class="suc-header">
          <div class="suc-nombre">📍 {info['nombre_sucursal']}</div>
        </div>""",
        unsafe_allow_html=True
    )
    if st.button("🚪 Cerrar sesión", use_container_width=False):
        st.session_state.clear()
        st.query_params.clear()
        st.rerun()

    st.divider()

    df_maestro         = obtener_maestro_productos()
    lista_prod_nombres = df_maestro['nombre'].tolist()

    menu = (
        ["📝 Pedido", "📊 General", "📜 Historial", "👥 Usuarios", "📦 Catálogo"]
        if es_admin else
        ["📝 Pedido", "📜 Historial"]
    )
    tabs = st.tabs(menu)

    # ── TAB 0: PEDIDO ───────────────────────────
    with tabs[0]:
        render_pedido(uid, lista_prod_nombres)

    if es_admin:

        # ── TAB 1: PEDIDO GENERAL ───────────────
        with tabs[1]:
            res = supabase.table("pedidos") \
                .select("id, producto, cantidad, unidad_medida, usuarios(nombre_sucursal)") \
                .eq("estado", "pendiente").execute()

            if res.data:
                df_raw = pd.json_normalize(res.data)
                df_res = df_raw.groupby(['producto', 'unidad_medida'])['cantidad'] \
                               .sum().reset_index()
                df_res = df_res.merge(df_maestro, left_on='producto',
                                      right_on='nombre', how='left').sort_values('orden')
                df_final = df_res[['producto', 'unidad_medida', 'cantidad']].rename(
                    columns={'producto': 'Producto', 'unidad_medida': 'Unidad', 'cantidad': 'Total'})

                st.dataframe(df_final.style.format({"Total": "{:.1f}"}),
                             use_container_width=True, hide_index=True)

                c_p1, c_p2 = st.columns(2)
                with c_p1:
                    st.download_button("📄 PDF Compra",
                        data=generar_pdf("LISTA DE COMPRA", df_final),
                        file_name=f"compra_{datetime.now().strftime('%d_%m')}.pdf",
                        mime="application/pdf", type="primary", use_container_width=True)
                with c_p2:
                    st.download_button("🚚 PDF Reparto",
                        data=generar_pdf_detallado("DETALLE DE REPARTO", df_raw),
                        file_name=f"reparto_{datetime.now().strftime('%d_%m')}.pdf",
                        mime="application/pdf", type="primary", use_container_width=True)

                st.divider()
                if "confirmar_limpieza" not in st.session_state:
                    st.session_state.confirmar_limpieza = False

                if not st.session_state.confirmar_limpieza:
                    if st.button("✅ FINALIZAR Y LIMPIAR DÍA", type="primary",
                                 use_container_width=True):
                        st.session_state.confirmar_limpieza = True
                        st.rerun()
                else:
                    st.warning("⚠️ ¿Estás seguro? Esto marcará todos los pedidos como completados.")
                    col_si, col_no = st.columns(2)
                    with col_si:
                        if st.button("✅ Sí, limpiar", type="primary", use_container_width=True):
                            supabase.table("pedidos").update({"estado": "completado"}) \
                                .in_("id", df_raw['id'].tolist()).execute()
                            st.session_state.confirmar_limpieza = False
                            st.success("Limpieza completada.")
                            time.sleep(1)
                            st.rerun()
                    with col_no:
                        if st.button("❌ Cancelar", use_container_width=True):
                            st.session_state.confirmar_limpieza = False
                            st.rerun()
            else:
                st.info("No hay pedidos pendientes.")

        # ── TAB 3: USUARIOS ─────────────────────
        with tabs[3]:
            st.subheader("👥 Usuarios")
            with st.expander("➕ Nueva Sucursal"):
                with st.form("ns"):
                    nu     = st.text_input("Usuario")
                    np_raw = st.text_input("Clave")
                    ns_txt = st.text_input("Nombre Sucursal")
                    if st.form_submit_button("Crear", type="primary"):
                        if nu and np_raw and ns_txt:
                            supabase.table("usuarios").insert({
                                "username":        nu,
                                "password":        hashear_password(np_raw),
                                "nombre_sucursal": ns_txt,
                                "rol":             "sucursal"
                            }).execute()
                            st.success(f"Sucursal '{ns_txt}' creada.")
                            st.rerun()
                        else:
                            st.warning("Completá todos los campos.")
            res_u = supabase.table("usuarios").select("*").execute()
            render_usuarios(res_u.data)

        # ── TAB 4: CATÁLOGO ─────────────────────
        with tabs[4]:
            st.subheader("📦 Catálogo")
            with st.form("np"):
                n_p = st.text_input("Nuevo producto")
                if st.form_submit_button("Añadir", type="primary"):
                    if n_p.strip():
                        supabase.table("productos_lista").insert({
                            "nombre": n_p.strip().capitalize(),
                            "orden":  len(df_maestro)
                        }).execute()
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.warning("Ingresá un nombre válido.")
            st.divider()
            render_catalogo(df_maestro)

    # ── TAB HISTORIAL ───────────────────────────
    hist_idx = 2 if es_admin else 1
    with tabs[hist_idx]:
        st.subheader("📜 Historial")
        query = supabase.table("pedidos").select(
            "fecha_pedido, producto, cantidad, unidad_medida, estado, usuarios(nombre_sucursal)"
        )
        if not es_admin:
            query = query.eq("usuario_id", uid)
        hist = query.order("fecha_pedido", desc=True).limit(300).execute()

        if hist.data:
            df_h             = pd.json_normalize(hist.data)
            df_h['fecha_dt'] = pd.to_datetime(df_h['fecha_pedido'])

            def calc_sem(f):
                l = f - timedelta(days=f.weekday())
                d = l + timedelta(days=6)
                return f"Semana {l.strftime('%d/%m')} al {d.strftime('%d/%m')}"

            df_h['Rango'] = df_h['fecha_dt'].apply(calc_sem)
            for rango in df_h['Rango'].unique():
                with st.expander(f"📅 {rango}"):
                    df_s = df_h[df_h['Rango'] == rango].copy()
                    cols = (
                        ['usuarios.nombre_sucursal', 'producto', 'cantidad',
                         'unidad_medida', 'estado']
                        if es_admin else
                        ['producto', 'cantidad', 'unidad_medida', 'estado']
                    )
                    cols = [c for c in cols if c in df_s.columns]
                    st.dataframe(
                        df_s[cols].rename(columns={
                            'usuarios.nombre_sucursal': 'Sucursal',
                            'producto':      'Producto',
                            'cantidad':      'Cant.',
                            'unidad_medida': 'Unidad',
                            'estado':        'Estado'
                        }),
                        hide_index=True, use_container_width=True
                    )
        else:
            st.info("No hay historial.")