import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import re
from datetime import datetime, timedelta
import io

# --- 1. CONFIGURACIÓN ---
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
        if not sh: return {}, {"usuarios": {"ADMIN": "123"}, "depositos": ["BODEGA"], "marcas": ["GENERAL"]}, [], None
        
        # Inventario
        ws_inv = sh.worksheet("INVENTARIO")
        datos_inv = ws_inv.get_all_records()
        inv = {f"{r['DEPOSITO']}_{r['CODIGO']}": {"marca": r['MARCA'], "deposito": r['DEPOSITO'], "stock": int(r['STOCK'])} for r in datos_inv if r.get('CODIGO')}
        
        # Configuración
        ws_conf = sh.worksheet("CONFIG")
        df_conf = pd.DataFrame(ws_conf.get_all_records())
        config = {
            "usuarios": {str(r['USUARIO']): str(r['CLAVE']) for _, r in df_conf.iterrows() if r.get('USUARIO')},
            "depositos": [x for x in df_conf['DEPOSITOS'].unique() if x] if 'DEPOSITOS' in df_conf else ["BODEGA"],
            "marcas": [x for x in df_conf['MARCAS'].unique() if x] if 'MARCAS' in df_conf else ["GENERAL"]
        }
        
        # Logs
        ws_log = sh.worksheet("LOGS")
        logs = ws_log.get_all_records()[-20:]
        logs.reverse()
        
        return inv, config, logs, sh
    except Exception as e:
        st.error(f"⚠️ Error al leer datos: {e}")
        return {}, {"usuarios": {"ADMIN": "123"}, "depositos": ["BODEGA"], "marcas": ["GENERAL"]}, [], None

# --- 2. INICIO DE LA APP ---
st.set_page_config(page_title="Bodega Pro Ultra", layout="wide")

# Estilos visuales
st.markdown("""<style>
    .block-container {padding-top: 1rem;}
    .stButton>button {width: 100%;}
</style>""", unsafe_allow_html=True)

# Carga de datos
if 'data_loaded' not in st.session_state:
    st.session_state.inv, st.session_state.config, st.session_state.logs, st.session_state.sh = cargar_datos_google()
    st.session_state.data_loaded = True

inv = st.session_state.inv
config = st.session_state.config
logs = st.session_state.logs
sh = st.session_state.sh

# Variables de estado
if 'edit_mode' not in st.session_state: st.session_state.edit_mode = False
if 'modo_panel' not in st.session_state: st.session_state.modo_panel = False

# --- 3. INTERFAZ ---
st.title("🏢 Sistema de Bodega")

# Buscador Principal
busq = st.text_input("🔍 BUSCAR CÓDIGO", placeholder="Escriba el código...").upper().strip()
if busq:
    resultados = {k: v for k, v in inv.items() if busq in k}
    if resultados:
        for k, v in resultados.items():
            st.success(f"✅ **{v['deposito']}**: {v['marca']} - {k.split('_')[-1]} | STOCK: {v['stock']}")
    else:
        st.warning("No se encontró el código.")

# --- SIDEBAR (LOGIN) ---
with st.sidebar:
    st.header("🔐 Acceso")
    if not st.session_state.edit_mode:
        u = st.selectbox("Usuario", list(config["usuarios"].keys()))
        p = st.text_input("Clave", type="password")
        if st.button("Entrar"):
            if config["usuarios"].get(u) == p:
                st.session_state.edit_mode = True
                st.session_state.usuario_actual = u
                st.rerun()
    else:
        st.write(f"👤 Usuario: **{st.session_state.usuario_actual}**")
        if st.button("Cerrar Sesión"):
            st.session_state.edit_mode = False
            st.rerun()
