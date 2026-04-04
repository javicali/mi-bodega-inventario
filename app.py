import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import re
from datetime import datetime, timedelta
import io

# --- CONFIGURACIÓN GOOGLE SHEETS ---
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
    except Exception as e:
        st.error(f"❌ Error de conexión: {e}")
        return None

def cargar_datos_google():
    try:
        sh = conectar_google()
        if not sh: return {}, {"usuarios": {"ADMIN": "123"}, "depositos": ["SETAR"], "marcas": ["IRUN"]}, [], None
        
        # 1. Inventario
        ws_inv = sh.worksheet("INVENTARIO")
        datos_inv = ws_inv.get_all_records()
        inv = {f"{r['DEPOSITO']}_{r['CODIGO']}": {"marca": r['MARCA'], "deposito": r['DEPOSITO'], "stock": int(r['STOCK'])} for r in datos_inv if r.get('CODIGO')}
        
        # 2. Configuración
        ws_conf = sh.worksheet("CONFIG")
        df_conf = pd.DataFrame(ws_conf.get_all_records())
        config = {
            "usuarios": {str(r['USUARIO']): str(r['CLAVE']) for _, r in df_conf.iterrows() if r.get('USUARIO')},
            "depositos": [x for x in df_conf['DEPOSITOS'].unique() if x] if 'DEPOSITOS' in df_conf else ["SETAR"],
            "marcas": [x for x in df_conf['MARCAS'].unique() if x] if 'MARCAS' in df_conf else ["IRUN"]
        }
        
        # 3. Logs
        ws_log = sh.worksheet("LOGS")
        logs = ws_log.get_all_records()[-50:]
        logs.reverse()
        
        return inv, config, logs, sh
    except Exception as e:
        st.error(f"⚠️ Error al leer hojas: {e}")
        return {}, {"usuarios": {"ADMIN": "123"}, "depositos": ["SETAR"], "marcas": ["IRUN"]}, [], None

def guardar_cambio_google(sh, tab, accion, datos):
    try:
        ws = sh.worksheet(tab)
        if accion == "UPDATE_STOCK":
            # datos = [id_f, nuevo_stock]
            depo, cod = datos[0].split("_", 1)
            celda = ws.find(cod)
            if celda: ws.update_cell(celda.row, 4, datos[1])
        elif accion == "ADD_LOG":
            # datos = [usuario, accion, detalle]
            hora = (datetime.now() - timedelta(hours=4)).strftime("%d/%m/%Y %H:%M")
            ws.append_row([hora] + datos)
        elif accion == "NUEVO_ITEM":
            # datos = [marca, depo, codigo, stock]
            ws.append_row(datos)
    except:
        st.error("Error al sincronizar con Google Sheets")

# --- INICIO APP ---
st.set_page_config(page_title="Bodega Pro Ultra", layout="wide")

# Estilos
st.markdown("""<style>
    .block-container {padding-top: 1rem;}
    .stButton>button {padding: 0.2rem 0.5rem; width: 100%;}
    small { color: #888; }
</style>""", unsafe_allow_html=True)

# Cargar Datos Globales
if 'data_loaded' not in st.session_state:
    st.session_state.inv, st.session_state.config, st.session_state.logs, st.session_state.sh = cargar_datos_google()
    st.session_state.data_loaded = True

inv, config, logs, sh = st.session_state.inv, st.session_state.config, st.session_state.logs, st.session_state.sh

if 'modo_panel' not in st.session_state: st.session_state.modo_panel = False
if 'edit_mode' not in st.session_state: st.session_state.edit_mode = False

# --- FUNCIÓN TARJETA DE EDICIÓN ---
def mostrar_item_edicion(id_f, info, sufijo):
    cod_l = id_f.split("_", 1)[1] if "_" in id_f else id_f
    with st.container(border=True):
        c1, c2, c3 = st.columns([1.5, 1, 2.2])
        c1.markdown(f"**{cod_l}**\n<small>{info['marca']} | {info['deposito']}</small>", unsafe_allow_html=True)
        c2.markdown(f"📦 **{info['stock']}**", unsafe_allow_html=True)
        
        with c3:
            cant = st.number_input("n", min_value=1, value=1, key=f"n_{sufijo}_{id_f}", label_visibility="collapsed")
            b1, b2 = st.columns(2)
            if b1.button("➕", key=f"add_{sufijo}_{id_f}"):
                inv[id_f]["stock"] += cant
                guardar_cambio_google(sh, "INVENTARIO", "UPDATE_STOCK", [id_f, inv[id_f]["stock"]])
                guardar_cambio_google(sh, "LOGS", "ADD_LOG", [st.session_state.usuario_actual, "SUMA", f"+{cant} {cod_l}"])
                st.rerun()
            if b2.button("➖", key=f"sub_{sufijo}_{id_f}", disabled=info['stock']<cant):
                inv[id_f]["stock"] -= cant
                guardar_cambio_google(sh, "INVENTARIO", "UPDATE_STOCK", [id_f, inv[id_f]["stock"]])
                guardar_cambio_google(sh, "LOGS", "ADD_LOG", [st.session_state.usuario_actual, "RESTA", f"-{cant} {cod_l}"])
                st.rerun()

# --- INTERFAZ PRINCIPAL ---
if not st.session_state.modo_panel:
    st.title("🏢 Consulta de Inventario")
    busq = st.text_input("Buscar código:", placeholder="Ingrese código...").upper().strip()
    if busq:
        res = {k: v for k, v in inv.items() if (k.split("_", 1)[1] if "_" in k else k) == busq}
        for k, v in res.items():
            if v['stock'] > 0: st.success(f"✅ **{v['deposito']}**: {v['marca']} - {busq} | Stock: {v['stock']}")
            else: st.error(f"🚨 AGOTADO en {v['deposito']}: {v['marca']} - {busq}")
    
    st.divider()
    if st.checkbox("👁️ Ver Stock General"):
        d_v = st.selectbox("Seleccione Depósito:", config["depositos"])
        tbs = st.tabs(config["marcas"])
        for i, m in enumerate(config["marcas"]):
            with tbs[i]:
                items = {k: v for k, v in inv.items() if v['marca']==m and v['deposito']==d_v}
                for kid, info in sorted(items.items()):
                    st.write(f"**{kid.split('_')[-1]}**: {info['stock']} cajas")

else:
    st.title("🛠️ Panel de Control")
    dep_p = st.selectbox("📍 Depósito de trabajo:", config["depositos"])
    tabs_p = st.tabs(config["marcas"] + ["⚠️ AGOTADOS"])
    for i, m_p in enumerate(config["marcas"]):
        with tabs_p[i]:
            it_p = {k: v for k, v in inv.items() if v['marca']==m_p and v['deposito']==dep_p and v['stock']>0}
            for k, v in sorted(it_p.items()): mostrar_item_edicion(k, v, f"tab_{i}")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔐 Acceso")
    if not st.session_state.edit_mode:
        u_log = st.selectbox("Usuario", list(config["usuarios"].keys()))
        p_log = st.text_input("Clave", type="password")
        if st.button("🔓 Entrar"):
            if config["usuarios"].get(u_log) == p_log:
                st.session_state.edit_mode, st.session_state.usuario_actual = True, u_log
                st.rerun()
    else:
        st.success(f"👤 {st.session_state.usuario_actual}")
        if st.button("⚙️ PANEL CONTROL" if not st.session_state.modo_panel else "🏠 VISTA INICIO"):
            st.session_state.modo_panel = not st.session_state.modo_panel
            st.rerun()
        
        with st.expander("🆕 Nuevo Código"):
            n_m = st.selectbox("Marca", config["marcas"])
            n_c = st.text_input("Código").upper().strip()
            n_d = st.selectbox("Depósito", config["depositos"])
            if st.button("💾 Crear"):
                if n_c:
                    guardar_cambio_google(sh, "INVENTARIO", "NUEVO_ITEM", [n_m, n_d, n_c, 0])
                    st.session_state.clear(); st.rerun()

        if st.button("🔒 Salir"):
            st.session_state.edit_mode = False; st.rerun()

    st.divider()
    st.caption("Conectado a Google Sheets")
