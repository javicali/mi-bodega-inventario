import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime, timedelta
import io

# --- 1. CONFIGURACIÓN DE GOOGLE SHEETS ---
NOMBRE_EXCEL = "DB_BODEGA_SISTEMA"
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def conectar_google():
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            if "private_key" in creds_dict:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name('creds.json', SCOPE)
        return gspread.authorize(creds).open(NOMBRE_EXCEL)
    except: return None

def cargar_datos_google():
    def_config = {"usuarios": {"ADMIN": "123"}, "depositos": ["PRINCIPAL"], "marcas": ["GENERAL"]}
    try:
        sh = conectar_google()
        if not sh: return {}, def_config, [], None
        ws_inv = sh.worksheet("INVENTARIO")
        datos_inv = ws_inv.get_all_records()
        inv = {f"{r['DEPOSITO']}_{r['CODIGO']}": {"marca": r['MARCA'], "deposito": r['DEPOSITO'], "stock": int(r['STOCK'])} 
               for r in datos_inv if str(r.get('CODIGO')).strip()}
        ws_conf = sh.worksheet("CONFIG")
        df_conf = pd.DataFrame(ws_conf.get_all_records())
        list_users = {str(r['USUARIO']).strip(): str(r['CLAVE']).strip() for _, r in df_conf.iterrows() if str(r.get('USUARIO')).strip()}
        list_depos = [x for x in df_conf['DEPOSITOS'].unique() if str(x).strip()] if 'DEPOSITOS' in df_conf else []
        list_marcas = [x for x in df_conf['MARCAS'].unique() if str(x).strip()] if 'MARCAS' in df_conf else []
        config = {"usuarios": list_users if list_users else def_config["usuarios"],
                  "depositos": list_depos if list_depos else def_config["depositos"],
                  "marcas": list_marcas if list_marcas else def_config["marcas"]}
        ws_log = sh.worksheet("LOGS")
        logs_data = ws_log.get_all_records()
        return inv, config, logs_data, sh
    except: return {}, def_config, [], None

def guardar_cambio_google(sh, tab, accion, datos):
    try:
        ws = sh.worksheet(tab)
        if accion == "UPDATE_STOCK":
            celda = ws.find(datos[0].split("_")[-1])
            if celda: 
                ws.update_cell(celda.row, 4, datos[1])
                st.toast(f"✅ Stock actualizado", icon="📦")
        elif accion == "ADD_LOG":
            hora = (datetime.now() - timedelta(hours=4)).strftime("%d/%m/%Y %H:%M")
            ws.append_row([hora] + datos)
    except: st.error("⚠️ Error de conexión")

def txt_cajas(n):
    return f"{n} caja" if n == 1 else f"{n} cajas"

# --- 2. INICIALIZACIÓN ---
st.set_page_config(page_title="Bodega Inventario", layout="wide")

if 'busqueda_interna' not in st.session_state:
    st.session_state.busqueda_interna = ""

def recargar():
    st.session_state.inv, st.session_state.config, st.session_state.logs, st.session_state.sh = cargar_datos_google()

if 'data_loaded' not in st.session_state:
    recargar()
    st.session_state.data_loaded = True

inv, config, logs, sh = st.session_state.inv, st.session_state.config, st.session_state.logs, st.session_state.sh

# --- FUNCION EXCEL ---
def generar_excel(datos_inv):
    df = pd.DataFrame([
        {"BODEGA": v["deposito"], "MARCA": v["marca"], "CODIGO": k.split("_")[-1], "STOCK": v["stock"]}
        for k, v in datos_inv.items()
    ])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Inventario')
    return output.getvalue()

# --- DIALOGOS ---
@st.dialog("Confirmar")
def confirmar_mov(k, v, cant, op):
    st.warning(f"¿Confirmas {op} {txt_cajas(cant)}?")
    if st.button("SÍ, GUARDAR", use_container_width=True):
        nuevo = v['stock'] + cant if op == 'SUMAR' else v['stock'] - cant
        guardar_cambio_google(sh, "INVENTARIO", "UPDATE_STOCK", [k, nuevo])
        guardar_cambio_google(sh, "LOGS", "ADD_LOG", [st.session_state.usuario_actual, op, f"{cant} de {k}"])
        recargar(); st.rerun()

def mostrar_tarjeta(k, v, suf):
    with st.container(border=True):
        c1, c2, c3 = st.columns([2, 1, 3])
        c1.markdown(f"**{k.split('_')[-1]}**\n<small>{v['marca']}</small>", unsafe_allow_html=True)
        c2.write(f"📦 {v['stock']}")
        with c3:
            cant = st.number_input("n", min_value=1, key=f"n_{suf}_{k}", label_visibility="collapsed")
            col1, col2 = st.columns(2)
            if col1.button("➕", key=f"a_{suf}_{k}"): confirmar_mov(k, v, cant, "SUMAR")
            if col2.button("➖", key=f"s_{suf}_{k}", disabled=v['stock']<cant): confirmar_mov(k, v, cant, "RESTAR")

# --- 3. INTERFAZ ---
st.title("🏢 Bodega Sistema")

if not st.session_state.get('modo_panel', False):
    # --- BUSCADOR ---
    st.subheader("🔍 Consulta")
    c_in, c_bt = st.columns([4, 1])
    with c_in:
        bus_val = st.text_input("Buscar:", value=st.session_state.busqueda_interna, placeholder="Código...", label_visibility="collapsed").upper().strip()
        st.session_state.busqueda_interna = bus_val
    with c_bt:
        if st.button("🔍 OK", use_container_width=True): st.rerun()

    if st.session_state.busqueda_interna:
        bus = st.session_state.busqueda_interna
        encontrados = {k: v for k, v in inv.items() if bus in k}
        for k, v in encontrados.items():
            color = "green" if v['stock'] > 0 else "red"
            st.markdown(f"""<div style="border: 2px solid {color}; padding:10px; border-radius:10px; margin-bottom:10px;">
                <h4>📦 {k.split('_')[-1]}</h4>
                <p>Stock: <b>{v['stock']}</b> | {v['deposito']}</p>
            </div>""", unsafe_allow_html=True)
        if st.button("🗑️ Limpiar"): st.session_state.busqueda_interna = ""; st.rerun()

    st.divider()
    if st.button("📦 VER TODO EL STOCK", use_container_width=True):
        st.session_state.ver_todo = not st.session_state.get('ver_todo', False); st.rerun()

    if st.session_state.get('ver_todo', False):
        dep_v = st.selectbox("Bodega:", config["depositos"])
        for k, v in sorted(inv.items()):
            if v['deposito'] == dep_v and v['stock'] > 0:
                st.write(f"🔹 **{k.split('_')[-1]}** | {v['marca']} | **{v['stock']}**")

else:
    # --- PANEL ---
    st.header("🛠️ Panel de Edición")
    
    # Botón Reporte
    data_xls = generar_excel(inv)
    st.download_button(
        label="📊 DESCARGAR REPORTE MENSUAL",
        data=data_xls,
        file_name=f"Inventario_{datetime.now().strftime('%d_%m_%Y')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
    
    st.divider()
    dep_e = st.selectbox("Bodega:", config["depositos"], key="dep_e")
    tabs = st.tabs(config["marcas"])
    for i, m in enumerate(config["marcas"]):
        with tabs[i]:
            items = {k: v for k, v in inv.items() if v['marca']==m and v['deposito']==dep_e}
            for k, v in sorted(items.items()): mostrar_tarjeta(k, v, f"t_{i}")

# --- SIDEBAR ---
with st.sidebar:
    if not st.session_state.get('edit_mode', False):
        u = st.selectbox("Usuario", list(config["usuarios"].keys()))
        p = st.text_input("Clave", type="password")
        if st.button("🔓 Entrar"):
            if config["usuarios"].get(u) == p:
                st.session_state.edit_mode, st.session_state.usuario_actual = True, u
                st.rerun()
    else:
        st.write(f"👤 {st.session_state.usuario_actual}")
        if st.button("⚙️ PANEL / 🏠 INICIO", use_container_width=True):
            st.session_state.modo_panel = not st.session_state.get('modo_panel', False); st.rerun()
        
        if st.button("🔒 Salir", use_container_width=True):
            st.session_state.edit_mode = False; st.session_state.modo_panel = False; st.rerun()
