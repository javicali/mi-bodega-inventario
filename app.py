import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime, timedelta

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
        return {}, {"usuarios": {"ADMIN": "123"}, "depositos": ["BODEGA"], "marcas": ["GENERAL"]}, [], None

def guardar_cambio_google(sh, tab, accion, datos):
    try:
        ws = sh.worksheet(tab)
        if accion == "UPDATE_STOCK":
            depo, cod = datos[0].split("_", 1)
            # Busca el código en la columna C (3)
            celda = ws.find(cod)
            if celda: ws.update_cell(celda.row, 4, datos[1])
        elif accion == "ADD_LOG":
            hora = (datetime.now() - timedelta(hours=4)).strftime("%d/%m/%Y %H:%M")
            ws.append_row([hora] + datos)
        elif accion == "NUEVO_ITEM":
            ws.append_row(datos)
        elif accion == "ADD_CONFIG":
            # datos = [valor, columna] (3 para depo, 4 para marca)
            col = datos[1]
            filas = len(ws.col_values(col)) + 1
            ws.update_cell(filas, col, datos[0])
    except:
        st.error("Error al sincronizar con Google")

# --- 2. INICIO DE LA APP ---
st.set_page_config(page_title="Bodega Pro Ultra", layout="wide")

# Carga de datos
if 'data_loaded' not in st.session_state:
    st.session_state.inv, st.session_state.config, st.session_state.logs, st.session_state.sh = cargar_datos_google()
    st.session_state.data_loaded = True

inv, config, logs, sh = st.session_state.inv, st.session_state.config, st.session_state.logs, st.session_state.sh

if 'edit_mode' not in st.session_state: st.session_state.edit_mode = False
if 'modo_panel' not in st.session_state: st.session_state.modo_panel = False

# --- 3. INTERFAZ ---
st.title("🏢 Sistema de Bodega")

if not st.session_state.modo_panel:
    # VISTA CONSULTA
    busq = st.text_input("🔍 BUSCAR CÓDIGO", placeholder="Escriba el código...").upper().strip()
    if busq:
        resultados = {k: v for k, v in inv.items() if busq in k}
        if resultados:
            for k, v in resultados.items():
                if v['stock'] > 0: st.success(f"✅ **{v['deposito']}**: {v['marca']} - {k.split('_')[-1]} | STOCK: {v['stock']}")
                else: st.error(f"🚨 AGOTADO en {v['deposito']}: {v['marca']} - {k.split('_')[-1]}")
        else: st.warning("No se encontró el código.")

    if st.checkbox("👁️ Ver Todo el Inventario"):
        d_v = st.selectbox("Seleccione Depósito:", config["depositos"])
        tbs = st.tabs(config["marcas"])
        for i, m in enumerate(config["marcas"]):
            with tbs[i]:
                items = {k: v for k, v in inv.items() if v['marca']==m and v['deposito']==d_v}
                if items:
                    for kid, info in sorted(items.items()):
                        st.write(f"**{kid.split('_')[-1]}**: {info['stock']} cajas")
                else: st.write("No hay productos registrados.")

else:
    # VISTA PANEL DE CONTROL
    st.header("🛠️ Panel de Edición")
    dep_p = st.selectbox("📍 Depósito de trabajo:", config["depositos"])
    tabs_p = st.tabs(config["marcas"])
    for i, m_p in enumerate(config["marcas"]):
        with tabs_p[i]:
            it_p = {k: v for k, v in inv.items() if v['marca']==m_p and v['deposito']==dep_p}
            for k, v in sorted(it_p.items()):
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 1, 2])
                    c1.write(f"**{k.split('_')[-1]}**")
                    c2.write(f"📦 {v['stock']}")
                    with c3:
                        cant = st.number_input("Cant", min_value=1, value=1, key=f"n_{k}", label_visibility="collapsed")
                        b1, b2 = st.columns(2)
                        if b1.button("➕", key=f"add_{k}"):
                            v['stock'] += cant
                            guardar_cambio_google(sh, "INVENTARIO", "UPDATE_STOCK", [k, v['stock']])
                            guardar_cambio_google(sh, "LOGS", "ADD_LOG", [st.session_state.usuario_actual, "SUMA", f"+{cant} {k}"])
                            st.rerun()
                        if b2.button("➖", key=f"sub_{k}", disabled=v['stock']<cant):
                            v['stock'] -= cant
                            guardar_cambio_google(sh, "INVENTARIO", "UPDATE_STOCK", [k, v['stock']])
                            guardar_cambio_google(sh, "LOGS", "ADD_LOG", [st.session_state.usuario_actual, "RESTA", f"-{cant} {k}"])
                            st.rerun()

# --- SIDEBAR (GESTIÓN) ---
with st.sidebar:
    st.header("🔐 Acceso")
    if not st.session_state.edit_mode:
        u = st.selectbox("Usuario", list(config["usuarios"].keys()))
        p = st.text_input("Clave", type="password")
        if st.button("Entrar"):
            if config["usuarios"].get(u) == p:
                st.session_state.edit_mode, st.session_state.usuario_actual = True, u
                st.rerun()
    else:
        st.success(f"👤 {st.session_state.usuario_actual}")
        if st.button("⚙️ PANEL CONTROL" if not st.session_state.modo_panel else "🏠 VISTA INICIO"):
            st.session_state.modo_panel = not st.session_state.modo_panel
            st.rerun()
        
        # --- GESTION DE MARCAS ---
        with st.expander("🏷️ Marcas"):
            for m in config["marcas"]:
                st.write(f"• {m}")
            st.divider()
            nueva_m = st.text_input("Nueva Marca:").upper().strip()
            if st.button("Añadir Marca"):
                if nueva_m:
                    guardar_cambio_google(sh, "CONFIG", "ADD_CONFIG", [nueva_m, 4])
                    st.session_state.clear(); st.rerun()

        # --- GESTION DE DEPOSITOS ---
        with st.expander("🏘️ Depósitos"):
            for d in config["depositos"]:
                st.write(f"📍 {d}")
            st.divider()
            nuevo_d = st.text_input("Nuevo Depósito:").upper().strip()
            if st.button("Añadir Depo"):
                if nuevo_d:
                    guardar_cambio_google(sh, "CONFIG", "ADD_CONFIG", [nuevo_d, 3])
                    st.session_state.clear(); st.rerun()

        with st.expander("🆕 Nuevo Código"):
            n_m = st.selectbox("Marca", config["marcas"], key="nm")
            n_c = st.text_input("Código", key="nc").upper().strip()
            n_d = st.selectbox("Depósito", config["depositos"], key="nd")
            if st.button("💾 Crear"):
                if n_c:
                    guardar_cambio_google(sh, "INVENTARIO", "NUEVO_ITEM", [n_m, n_d, n_c, 0])
                    st.session_state.clear(); st.rerun()

        if st.button("🔒 Salir"):
            st.session_state.edit_mode = False; st.rerun()
