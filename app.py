import streamlit as st
from supabase import create_client, Client
import pandas as pd
import time
import json
from datetime import timedelta, datetime
from fpdf import FPDF
import unicodedata
import hashlib
import streamlit.components.v1 as components

# ─────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(URL, KEY)

st.set_page_config(page_title="El Rey Verdu - Pedidos", layout="centered")

st.markdown("""
<style>
.stToolbarActionButton { display: none; }
h1 a, h2 a, h3 a, h4 a, h5 a, h6 a { display: none !important; }
[data-testid="stHeader"] { background: rgba(0,0,0,0); }
</style>
""", unsafe_allow_html=True)

UNIDADES = ["cajon/es", "bolsa/s", "unidad/es"]

# ─────────────────────────────────────────────
# CSS BASE COMPARTIDO (inyectado en cada iframe)
# ─────────────────────────────────────────────
CSS_BASE = """
<style>
* { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
body { background: transparent; padding: 0 2px; }

/* ── Tabla base ── */
table { width: 100%; border-collapse: collapse; table-layout: fixed; }

thead tr { background: #2e7d32; color: white; }
thead th {
    padding: 9px 4px;
    font-size: 13px;
    font-weight: 700;
    text-align: center;
}
thead th:first-child {
    text-align: left;
    padding-left: 10px;
    border-radius: 7px 0 0 7px;
}
thead th:last-child { border-radius: 0 7px 7px 0; }

tbody tr { border-bottom: 1px solid #f0f0f0; }
tbody tr:last-child { border-bottom: none; }
tbody tr:hover { background: #f9fbe7; }

td { padding: 5px 3px; vertical-align: middle; font-size: 14px; }
td:first-child { padding-left: 8px; font-weight: 600; line-height: 1.3; word-break: break-word; }

/* ── Inputs ── */
.inp-sel, .inp-txt, .inp-num {
    width: 100%;
    padding: 6px 4px;
    font-size: 12px;
    border: 1px solid #ccc;
    border-radius: 7px;
    background: white;
}
.inp-num { text-align: center; }
.inp-sel:focus, .inp-txt:focus, .inp-num:focus {
    outline: 2px solid #2e7d32;
    border-color: #2e7d32;
}

/* ── Botones ── */
.btn {
    width: 100%;
    padding: 7px 4px;
    border: none;
    border-radius: 7px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 600;
    white-space: nowrap;
}
.btn-up, .btn-down {
    background: #e8f5e9;
    color: #2e7d32;
    border: 1px solid #a5d6a7;
    font-size: 15px;
}
.btn-up:hover, .btn-down:hover { background: #c8e6c9; }

.btn-del {
    background: #ffebee;
    color: #c62828;
    border: 1px solid #ef9a9a;
}
.btn-del:hover { background: #ffcdd2; }

.btn-edit {
    background: #e3f2fd;
    color: #1565c0;
    border: 1px solid #90caf9;
}
.btn-edit:hover { background: #bbdefb; }

.btn-save {
    background: #2e7d32;
    color: white;
    padding: 9px;
    font-size: 14px;
    width: 100%;
    border-radius: 7px;
    border: none;
    cursor: pointer;
    margin-top: 8px;
}
.btn-save:hover { background: #1b5e20; }

.btn-cancel {
    background: #f5f5f5;
    color: #555;
    padding: 9px;
    font-size: 14px;
    width: 100%;
    border-radius: 7px;
    border: 1px solid #ccc;
    cursor: pointer;
    margin-top: 4px;
}

.btn-add {
    background: #e8f5e9;
    border: 1px solid #a5d6a7;
    border-radius: 7px;
    padding: 8px 12px;
    font-size: 13px;
    cursor: pointer;
    margin-top: 8px;
    width: 100%;
    color: #2e7d32;
    font-weight: 600;
}
.btn-add:hover { background: #c8e6c9; }

.btn-enviar {
    width: 100%;
    padding: 14px;
    background: #2e7d32;
    color: white;
    font-size: 16px;
    font-weight: 700;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    margin-top: 12px;
    letter-spacing: 0.5px;
}
.btn-enviar:active { background: #1b5e20; }

/* ── Formulario de edición inline ── */
.edit-form {
    background: #f9fbe7;
    border: 1px solid #c5e1a5;
    border-radius: 8px;
    padding: 12px;
    margin: 4px 0 8px 0;
}
.edit-form label { font-size: 12px; color: #555; margin-bottom: 2px; display: block; }
.edit-form input {
    width: 100%;
    padding: 7px 8px;
    border: 1px solid #ccc;
    border-radius: 6px;
    font-size: 13px;
    margin-bottom: 8px;
}
.edit-form input:focus { outline: 2px solid #2e7d32; }

/* ── Mensajes ── */
.msg-ok   { color: #2e7d32; font-weight:700; text-align:center; padding:10px; background:#e8f5e9; border-radius:7px; margin-top:8px; }
.msg-warn { color: #e65100; font-weight:600; text-align:center; padding:10px; background:#fff3e0; border-radius:7px; margin-top:8px; }

.divider { border: none; border-top: 1px solid #ddd; margin: 12px 0; }
.section-title { font-size: 14px; font-weight: 700; color: #333; margin: 12px 0 6px 0; }
.hint { font-size: 11px; color: #888; text-align: center; margin-top: 6px; }

/* ── Extras ── */
.extra-row {
    display: grid;
    grid-template-columns: 38fr 18fr 30fr 10fr;
    gap: 4px;
    align-items: center;
    margin-bottom: 5px;
    padding-bottom: 5px;
    border-bottom: 1px solid #f0f0f0;
}
</style>
"""

# ─────────────────────────────────────────────
# FUNCIONES SOPORTE
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
    if "user_id" in st.query_params and "user_info" not in st.session_state:
        u_id = st.query_params["user_id"]
        if isinstance(u_id, str) and len(u_id) == 36:
            try:
                res = supabase.table("usuarios").select("*").eq("id", u_id).execute()
                if res.data:
                    st.session_state["user_info"] = res.data[0]
            except Exception:
                pass

# ─────────────────────────────────────────────
# PDFs
# ─────────────────────────────────────────────
# --- FUNCIONES PDF CORREGIDAS PARA EVITAR Invalid binary data format ---

def generar_pdf(titulo, datos):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(190, 10, normalizar_texto(titulo), ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(90, 14, "Producto", 1)
    pdf.cell(40, 14, "Cant.", 1)
    pdf.cell(60, 14, "Unidad", 1, ln=True)
    pdf.set_font("Arial", "", 12)
    for _, r in datos.iterrows():
        pdf.cell(90, 14, normalizar_texto(r['Producto']), 1)
        pdf.cell(40, 14, f"{float(r['Total']):.1f}", 1)
        pdf.cell(60, 14, normalizar_texto(r['Unidad']), 1, ln=True)
    
    # CORRECCIÓN: Forzamos la salida a bytes para que Streamlit la acepte
    return bytes(pdf.output())

def generar_pdf_detallado(titulo, df_raw):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(190, 10, normalizar_texto(titulo), ln=True, align="C")
    pdf.ln(10)
    col_suc = 'usuarios.nombre_sucursal'
    if col_suc in df_raw.columns:
        for s in df_raw[col_suc].dropna().unique():
            pdf.set_font("Arial", "B", 14)
            pdf.set_fill_color(240, 240, 240)
            pdf.cell(190, 12, f"SUCURSAL: {normalizar_texto(str(s))}", 1, ln=True, fill=True)
            pdf.set_font("Arial", "B", 10)
            pdf.cell(100, 14, "Producto", 1)
            pdf.cell(45, 14, "Cantidad", 1)
            pdf.cell(45, 14, "Unidad", 1, ln=True)
            d_suc = df_raw[df_raw[col_suc] == s]
            pdf.set_font("Arial", "", 11)
            for _, r in d_suc.iterrows():
                pdf.cell(100, 14, normalizar_texto(r['producto']), 1)
                pdf.cell(45, 14, f"{float(r['cantidad']):.1f}", 1)
                pdf.cell(45, 14, normalizar_texto(r['unidad_medida']), 1, ln=True)
            pdf.ln(10)
            
    # CORRECCIÓN: Forzamos la salida a bytes para evitar el error de Streamlit
    return bytes(pdf.output())

# ─────────────────────────────────────────────
# GUARDAR PEDIDO
# ─────────────────────────────────────────────

def guardar_pedido(usuario_id, items):
    batch = []
    for it in items:
        cant   = validar_cantidad(it.get('cantidad', 0))
        nombre = str(it.get('producto', '')).strip()
        if nombre and cant > 0:
            batch.append({
                "usuario_id": usuario_id, "producto": nombre,
                "cantidad": cant, "unidad_medida": it.get('unidad_medida', 'cajon/es'),
                "estado": "pendiente"
            })
    if batch:
        supabase.table("pedidos").insert(batch).execute()
        return True
    return False

# ─────────────────────────────────────────────
# HTML: TABLA DE PEDIDO
# ─────────────────────────────────────────────

def html_tabla_pedido(productos):
    filas = ""
    for prod in productos:
        pid  = prod.replace(" ", "_").replace("/", "_")
        opts = "".join(f'<option value="{u}">{u}</option>' for u in UNIDADES)
        filas += f"""
        <tr>
          <td style="width:42%">{prod}</td>
          <td style="width:33%">
            <select name="unidad_{pid}" class="inp-sel">{opts}</select>
          </td>
          <td style="width:25%">
            <input type="number" name="cant_{pid}" class="inp-num"
                   placeholder="0" min="0" step="0.5" inputmode="decimal">
          </td>
        </tr>"""

    return CSS_BASE + f"""
<table>
  <thead><tr>
    <th style="width:42%; text-align:left; padding-left:10px">Producto</th>
    <th style="width:33%">Unidad</th>
    <th style="width:25%">Cant.</th>
  </tr></thead>
  <tbody>{filas}</tbody>
</table>

<hr class="divider">
<div class="section-title">✨ Productos Adicionales</div>
<div id="extras-wrap"></div>
<button class="btn-add" onclick="agregarExtra()">➕ Añadir producto adicional</button>
<hr class="divider">
<div id="msg"></div>
<button class="btn-enviar" onclick="enviar()">🚀 ENVIAR PEDIDO</button>
<div class="hint">Campos en 0 o vacíos no se envían</div>

<script>
const UNIDADES  = {json.dumps(UNIDADES)};
const PRODUCTOS = {json.dumps(productos)};
let extraCount  = 0;

function optsUnidad() {{
  return UNIDADES.map(u => `<option value="${{u}}">${{u}}</option>`).join('');
}}

function agregarExtra() {{
  const id  = extraCount++;
  const div = document.createElement('div');
  div.className = 'extra-row';
  div.id = 'ex_' + id;
  div.innerHTML = `
    <input class="inp-txt" type="text"   name="ex_nom_${{id}}"  placeholder="Producto" />
    <input class="inp-num" type="number" name="ex_cant_${{id}}" placeholder="0" min="0" step="0.5" inputmode="decimal"/>
    <select class="inp-sel" name="ex_unid_${{id}}">${{optsUnidad()}}</select>
    <button class="btn btn-del" type="button" onclick="document.getElementById('ex_${{id}}').remove()">🗑️</button>
  `;
  document.getElementById('extras-wrap').appendChild(div);
}}

function enviar() {{
  const items = [];

  for (const prod of PRODUCTOS) {{
    const pid  = prod.replaceAll(' ','_').replaceAll('/','_');
    const cEl  = document.querySelector('[name="cant_' + pid + '"]');
    const uEl  = document.querySelector('[name="unidad_' + pid + '"]');
    if (!cEl) continue;
    const c = parseFloat(cEl.value);
    if (!isNaN(c) && c > 0) {{
      items.push({{ producto: prod, cantidad: Math.round(c*2)/2, unidad_medida: uEl?.value || 'cajon/es' }});
    }}
  }}

  document.querySelectorAll('[id^="ex_"]').forEach(row => {{
    const id   = row.id.replace('ex_','');
    const nom  = (row.querySelector('[name="ex_nom_'+id+'"]')?.value || '').trim();
    const c    = parseFloat(row.querySelector('[name="ex_cant_'+id+'"]')?.value || '');
    const unid = row.querySelector('[name="ex_unid_'+id+'"]')?.value || 'cajon/es';
    if (nom && !isNaN(c) && c > 0) {{
      items.push({{ producto: nom, cantidad: Math.round(c*2)/2, unidad_medida: unid }});
    }}
  }});

  if (items.length === 0) {{
    document.getElementById('msg').innerHTML = '<div class="msg-warn">⚠️ No hay cantidades mayores a 0.</div>';
    return;
  }}
  document.getElementById('msg').innerHTML = '<div class="msg-ok">✅ Enviando pedido...</div>';
  window.parent.postMessage({{ type: 'streamlit:setComponentValue', value: JSON.stringify({{action:'pedido', items}}) }}, '*');
}}
</script>
"""

# ─────────────────────────────────────────────
# HTML: TABLA CATÁLOGO
# ─────────────────────────────────────────────

def html_tabla_catalogo(productos_df):
    filas = ""
    prods = productos_df.to_dict('records')
    for row in prods:
        nombre = row['nombre']
        rid    = str(row['id'])
        orden  = row['orden']
        filas += f"""
        <tr id="row_{rid}">
          <td style="width:55%">{nombre}</td>
          <td style="width:11%; text-align:center">
            <button class="btn btn-up" onclick="accion('up','{rid}',{orden})">🔼</button>
          </td>
          <td style="width:11%; text-align:center">
            <button class="btn btn-down" onclick="accion('down','{rid}',{orden})">🔽</button>
          </td>
          <td style="width:23%; text-align:center">
            <button class="btn btn-del" onclick="accion('del','{rid}',{orden})">Borrar</button>
          </td>
        </tr>"""

    return CSS_BASE + f"""
<table>
  <thead><tr>
    <th style="width:55%; text-align:left; padding-left:10px">Producto</th>
    <th style="width:11%">↑</th>
    <th style="width:11%">↓</th>
    <th style="width:23%">Acción</th>
  </tr></thead>
  <tbody id="tbody">{filas}</tbody>
</table>
<div id="msg"></div>

<script>
function accion(tipo, id, orden) {{
  document.getElementById('msg').innerHTML = '<div class="msg-ok" style="font-size:12px">Procesando...</div>';
  window.parent.postMessage({{
    type: 'streamlit:setComponentValue',
    value: JSON.stringify({{ action: 'catalogo', tipo, id, orden }})
  }}, '*');
}}
</script>
"""

# ─────────────────────────────────────────────
# HTML: TABLA USUARIOS
# ─────────────────────────────────────────────

def html_tabla_usuarios(usuarios):
    filas = ""
    for u in usuarios:
        uid    = str(u['id'])
        nombre = u['nombre_sucursal']
        login  = u['username']
        es_adm = u['rol'] == 'admin'
        btn_del = "" if es_adm else f'<button class="btn btn-del" onclick="accion(\'del\',\'{uid}\')">🗑️ Borrar</button>'
        filas += f"""
        <tr>
          <td style="width:52%">
            <span style="font-weight:700">{nombre}</span><br>
            <span style="font-size:11px; color:#888">{login}</span>
          </td>
          <td style="width:24%; text-align:center">
            <button class="btn btn-edit" onclick="mostrarEdit('{uid}','{nombre}','{login}')">✏️ Editar</button>
          </td>
          <td style="width:24%; text-align:center">
            {btn_del}
          </td>
        </tr>
        <tr id="edit_{uid}" style="display:none">
          <td colspan="3">
            <div class="edit-form">
              <label>Login</label>
              <input id="ed_u_{uid}" value="{login}" placeholder="Usuario">
              <label>Nueva clave <span style="color:#aaa">(vacío = no cambiar)</span></label>
              <input id="ed_p_{uid}" type="password" placeholder="••••••">
              <label>Nombre Sucursal</label>
              <input id="ed_s_{uid}" value="{nombre}" placeholder="Sucursal">
              <button class="btn-save" onclick="guardarEdit('{uid}')">💾 Guardar</button>
              <button class="btn-cancel" onclick="ocultarEdit('{uid}')">Cancelar</button>
            </div>
          </td>
        </tr>"""

    return CSS_BASE + f"""
<table>
  <thead><tr>
    <th style="width:52%; text-align:left; padding-left:10px">Sucursal / Usuario</th>
    <th style="width:24%">Editar</th>
    <th style="width:24%">Acción</th>
  </tr></thead>
  <tbody>{filas}</tbody>
</table>
<div id="msg"></div>

<script>
function mostrarEdit(uid, nombre, login) {{
  document.getElementById('edit_' + uid).style.display = '';
}}
function ocultarEdit(uid) {{
  document.getElementById('edit_' + uid).style.display = 'none';
}}
function guardarEdit(uid) {{
  const u = document.getElementById('ed_u_' + uid).value.trim();
  const p = document.getElementById('ed_p_' + uid).value;
  const s = document.getElementById('ed_s_' + uid).value.trim();
  if (!u || !s) {{
    document.getElementById('msg').innerHTML = '<div class="msg-warn">⚠️ Login y nombre son obligatorios.</div>';
    return;
  }}
  document.getElementById('msg').innerHTML = '<div class="msg-ok" style="font-size:12px">Guardando...</div>';
  window.parent.postMessage({{
    type: 'streamlit:setComponentValue',
    value: JSON.stringify({{ action:'usuarios', tipo:'edit', id:uid, username:u, password:p, nombre_sucursal:s }})
  }}, '*');
}}
function accion(tipo, uid) {{
  if (tipo === 'del') {{
    if (!confirm('¿Eliminar este usuario?')) return;
  }}
  document.getElementById('msg').innerHTML = '<div class="msg-ok" style="font-size:12px">Procesando...</div>';
  window.parent.postMessage({{
    type: 'streamlit:setComponentValue',
    value: JSON.stringify({{ action:'usuarios', tipo, id:uid }})
  }}, '*');
}}
</script>
"""

# ─────────────────────────────────────────────
# PROCESAR MENSAJES DE COMPONENTES
# ─────────────────────────────────────────────

def procesar_mensaje(resultado, usuario_id, df_maestro):
    """Recibe el JSON del componente HTML y ejecuta la acción correspondiente."""
    if resultado is None:
        return
    try:
        data = json.loads(resultado)
    except Exception:
        return

    accion = data.get('action')

    # ── Pedido ──────────────────────────────────
    if accion == 'pedido':
        items = data.get('items', [])
        if guardar_pedido(usuario_id, items):
            st.success("¡Pedido registrado correctamente!")
            time.sleep(1)
            st.rerun()
        else:
            st.warning("No hay productos con cantidad válida mayor a 0.")

    # ── Catálogo ─────────────────────────────────
    elif accion == 'catalogo':
        tipo, pid, orden = data['tipo'], data['id'], int(data.get('orden', -1))
        
        if tipo == 'del':
            # Borramos y limpiamos caché para que desaparezca de la vista al instante
            supabase.table("productos_lista").delete().eq("id", pid).execute()
            st.cache_data.clear() 
            st.rerun()

        elif tipo in ('up', 'down'):
            # Calculamos cuál es el orden del producto con el que queremos swappear
            target_orden = orden - 1 if tipo == 'up' else orden + 1
            if target_orden < 0: return

            # Buscamos al producto vecino directamente en la DB
            res_vecino = supabase.table("productos_lista").select("id").eq("orden", target_orden).execute()
            
            if res_vecino.data:
                vecino_id = res_vecino.data[0]['id']
                # Intercambiamos los valores de 'orden' entre ambos
                supabase.table("productos_lista").update({"orden": target_orden}).eq("id", pid).execute()
                supabase.table("productos_lista").update({"orden": orden}).eq("id", vecino_id).execute()
                
                # Limpiamos caché y refrescamos para ver el cambio
                st.cache_data.clear()
                st.rerun()

    # ── Usuarios ─────────────────────────────────
    elif accion == 'usuarios':
        tipo = data.get('tipo')
        uid  = data.get('id')

        if tipo == 'del':
            supabase.table("usuarios").delete().eq("id", uid).execute()
            st.rerun()

        elif tipo == 'edit':
            upd = {
                "username":        data.get('username', ''),
                "nombre_sucursal": data.get('nombre_sucursal', '')
            }
            pwd = data.get('password', '').strip()
            if pwd:
                upd["password"] = hashear_password(pwd)
            supabase.table("usuarios").update(upd).eq("id", uid).execute()
            st.success("Usuario actualizado.")
            st.rerun()

# ─────────────────────────────────────────────
# APP PRINCIPAL
# ─────────────────────────────────────────────

# --- REFUERZO DE SESIÓN ---
def check_session():
    # 1. Si ya existe la info en la memoria de Streamlit, no hacemos nada más
    if "user_info" in st.session_state:
        return

    # 2. Si no está en memoria pero sí en la URL, intentamos recuperarla de la DB
    u_id = st.query_params.get("user_id")
    if u_id:
        try:
            # Buscamos al usuario por su ID único (UUID)
            res = supabase.table("usuarios").select("*").eq("id", u_id).execute()
            if res.data:
                st.session_state["user_info"] = res.data[0]
        except Exception:
            pass

# Ejecutamos la verificación antes de renderizar cualquier cosa
check_session()

if "user_info" not in st.session_state:
    st.markdown("<h1 style='text-align:center'>📍 El Rey Verdu 📍<br>Pedidos</h1>", unsafe_allow_html=True)
    with st.form("login"):
        u = st.text_input("Usuario")
        p = st.text_input("Clave", type="password")
        if st.form_submit_button("Iniciar Sesión", type="primary", use_container_width=True):
            p_hash = hashear_password(p)
            # Intentamos primero con la clave hasheada
            res = supabase.table("usuarios").select("*").eq("username", u).eq("password", p_hash).execute()
            
            # Si falla, intentamos con texto plano (para compatibilidad con usuarios viejos)
            if not res.data:
                res = supabase.table("usuarios").select("*").eq("username", u).eq("password", p).execute()
            
            if res.data:
                st.session_state["user_info"] = res.data[0]
                # IMPORTANTE: Escribimos el ID en la URL para que persista al refrescar (F5)
                st.query_params["user_id"] = res.data[0]["id"]
                st.rerun()
            else:
                st.error("Acceso denegado. Verifique usuario y clave.")

else:
    info = st.session_state["user_info"]
    es_admin = info["rol"] == "admin"

    # Barra superior
    c_suc, c_out = st.columns([0.7, 0.3])
    with c_suc:
        st.markdown(f"### 📍 {info['nombre_sucursal']}")
    with c_out:
        if st.button("Cerrar Sesión", type="secondary", use_container_width=True):
            st.session_state.clear()
            st.query_params.clear()
            st.rerun()

    df_maestro         = obtener_maestro_productos()
    lista_prod_nombres = df_maestro['nombre'].tolist()

    menu = (
        ["📝 Cargar Pedido", "📊 Pedido General", "📜 Historial", "👥 Usuarios", "📦 Catálogo"]
        if es_admin else ["📝 Cargar", "📜 Historial"]
    )
    tabs = st.tabs(menu)

    # ════════════════════════════════════════════
    # TAB 0 — CARGAR PEDIDO
    # ════════════════════════════════════════════
    with tabs[0]:
        altura_pedido = max(420, len(lista_prod_nombres) * 50 + 280)
        res_pedido = components.html(
            html_tabla_pedido(lista_prod_nombres),
            height=altura_pedido,
            scrolling=False
        )
        procesar_mensaje(res_pedido, info["id"], df_maestro)

    # ════════════════════════════════════════════
    # TABS ADMIN
    # ════════════════════════════════════════════
    if es_admin:

        # TAB 1 — PEDIDO GENERAL
        with tabs[1]:
            res = supabase.table("pedidos") \
                .select("id, producto, cantidad, unidad_medida, usuarios(nombre_sucursal)") \
                .eq("estado", "pendiente").execute()

            if res.data:
                df_raw   = pd.json_normalize(res.data)
                df_res   = df_raw.groupby(['producto', 'unidad_medida'])['cantidad'].sum().reset_index()
                df_res   = df_res.merge(df_maestro, left_on='producto', right_on='nombre', how='left').sort_values('orden')
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
                    if st.button("✅ FINALIZAR Y LIMPIAR DÍA", type="primary", use_container_width=True):
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

        # TAB 3 — USUARIOS
        with tabs[3]:
            st.subheader("👥 Gestión de Usuarios")

            with st.expander("➕ Nueva Sucursal"):
                with st.form("ns"):
                    nu     = st.text_input("Usuario")
                    np_raw = st.text_input("Clave")
                    ns     = st.text_input("Nombre Sucursal")
                    if st.form_submit_button("Crear Cuenta", type="primary"):
                        if nu and np_raw and ns:
                            supabase.table("usuarios").insert({
                                "username": nu, "password": hashear_password(np_raw),
                                "nombre_sucursal": ns, "rol": "sucursal"
                            }).execute()
                            st.success(f"Sucursal '{ns}' creada.")
                            st.rerun()
                        else:
                            st.warning("Completá todos los campos.")

            res_u   = supabase.table("usuarios").select("*").execute()
            altura_u = max(200, len(res_u.data) * 72 + 60)
            res_comp_u = components.html(
                html_tabla_usuarios(res_u.data),
                height=altura_u,
                scrolling=False
            )
            procesar_mensaje(res_comp_u, info["id"], df_maestro)

        # TAB 4 — CATÁLOGO
        with tabs[4]:
            st.subheader("📦 Catálogo de Productos")

            with st.form("np"):
                n_p = st.text_input("Nombre de nuevo producto")
                if st.form_submit_button("Añadir al Catálogo", type="primary"):
                    if n_p.strip():
                        supabase.table("productos_lista").insert({
                            "nombre": n_p.strip().capitalize(),
                            "orden": len(df_maestro)
                        }).execute()
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.warning("Ingresá un nombre válido.")

            altura_cat = max(200, len(df_maestro) * 50 + 60)
            res_comp_cat = components.html(
                html_tabla_catalogo(df_maestro),
                height=altura_cat,
                scrolling=False
            )
            procesar_mensaje(res_comp_cat, info["id"], df_maestro)

    # ════════════════════════════════════════════
    # TAB HISTORIAL
    # ════════════════════════════════════════════
    hist_idx = 2 if es_admin else 1
    with tabs[hist_idx]:
        st.subheader("📜 Historial de Pedidos")
        query = supabase.table("pedidos").select(
            "fecha_pedido, producto, cantidad, unidad_medida, estado, usuarios(nombre_sucursal)"
        )
        if not es_admin:
            query = query.eq("usuario_id", info["id"])
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
                        ['usuarios.nombre_sucursal', 'producto', 'cantidad', 'unidad_medida', 'estado']
                        if es_admin else
                        ['producto', 'cantidad', 'unidad_medida', 'estado']
                    )
                    cols = [c for c in cols if c in df_s.columns]
                    st.dataframe(
                        df_s[cols].rename(columns={
                            'usuarios.nombre_sucursal': 'Sucursal',
                            'producto': 'Producto', 'cantidad': 'Cant.',
                            'unidad_medida': 'Unidad', 'estado': 'Estado'
                        }),
                        hide_index=True, use_container_width=True
                    )
        else:
            st.info("No hay historial registrado.")