import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime, timedelta

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
        config = {
            "usuarios": list_users if list_users else def_config["usuarios"],
            "depositos": list_depos if list_depos else def_config["depositos"],
            "marcas": list_marcas if list_marcas else def_config["marcas"]
        }
        ws_log = sh.worksheet("LOGS")
        logs_data = ws_log.get_all_records()
        return inv, config, logs_data, sh
    except: return {}, def_config, [], None

def guardar_cambio_google(sh, tab, accion, datos):
    try:
        ws = sh.worksheet(tab)
        if accion == "UPDATE_STOCK":
            depo, cod = datos[0].split("_", 1)
            celda = ws.find(cod)
            if celda: ws.update_cell(celda.row, 4, datos[1])
        elif accion == "ADD_LOG":
            hora = (datetime.now() - timedelta(hours=4)).strftime("%d/%m/%Y %H:%M")
            ws.append_row([hora] + datos)
        elif accion == "NUEVO_ITEM": ws.append_row(datos)
        elif accion == "ADD_CONFIG":
            col_vals = ws.col_values(datos[1])
            ws.update_cell(len(col_vals) + 1, datos[1], datos[0])
        elif accion == "DEL_CONFIG":
            celda = ws.find(datos[0])
            if celda and celda.col == datos[1]: ws.update_cell(celda.row, datos[1], "")
        elif accion == "RENAME_CONFIG":
            celda = ws.find(datos[0])
            if celda and celda.col == datos[2]: ws.update_cell(celda.row, datos[2], datos[1])
        elif accion == "MANAGE_USER":
            if datos[2] == "CREAR": ws.append_row([datos[0], datos[1]], value_input_option='RAW')
            elif datos[2] == "ELIMINAR":
                celda = ws.find(datos[0])
                if celda and celda.col == 1: ws.delete_rows(celda.row)
            elif datos[2] == "MODIFICAR":
                celda = ws.find(datos[0])
                if celda and celda.col == 1: ws.update_cell(celda.row, 2, datos[1])
    except: st.error("⚠️ Error de comunicación")

# --- 2. INICIALIZACIÓN ---
st.set_page_config(page_title="Bodega Pro Ultra", layout="wide")
if 'data_loaded' not in st.session_state:
    st.session_state.inv, st.session_state.config, st.session_state.logs, st.session_state.sh = cargar_datos_google()
    st.session_state.data_loaded = True

inv, config, logs, sh = st.session_state.inv, st.session_state.config, st.session_state.logs, st.session_state.sh
if 'edit_mode' not in st.session_state: st.session_state.edit_mode = False
if 'modo_panel' not in st.session_state: st.session_state.modo_panel = False
if 'ver_historial' not in st.session_state: st.session_state.ver_historial = False

def mostrar_tarjeta(k, v, suf):
    with st.container(border=True):
        c1, c2, c3 = st.columns([2, 1, 2.5])
        c1.markdown(f"**{k.split('_')[-1]}**\n<small>{v['marca']} | {v['deposito']}</small>", unsafe_allow_html=True)
        c2.write(f"📦 {v['stock']}")
        with c3:
            cant = st.number_input("n", min_value=1, key=f"n_{suf}_{k}", label_visibility="collapsed")
            b1, b2 = st.columns(2)
            if b1.button("➕", key=f"a_{suf}_{k}"):
                v['stock'] += cant
                guardar_cambio_google(sh, "INVENTARIO", "UPDATE_STOCK", [k, v['stock']])
                guardar_cambio_google(sh, "LOGS", "ADD_LOG", [st.session_state.usuario_actual, "ENTRADA", f"+{cant} {k}"])
                st.rerun()
            if b2.button("➖", key=f"s_{suf}_{k}", disabled=v['stock']<cant):
                v['stock'] -= cant
                guardar_cambio_google(sh, "INVENTARIO", "UPDATE_STOCK", [k, v['stock']])
                guardar_cambio_google(sh, "LOGS", "ADD_LOG", [st.session_state.usuario_actual, "SALIDA", f"-{cant} {k}"])
                st.rerun()

# --- 3. INTERFAZ ---
st.title("🏢 Sistema de Bodega")

if st.session_state.ver_historial:
    st.header("📜 Historial")
    if st.button("⬅️ Volver"): st.session_state.ver_historial = False; st.rerun()
    st.dataframe(pd.DataFrame(logs).iloc[::-1], use_container_width=True)

elif not st.session_state.modo_panel:
    # --- VISTA CONSULTA ---
    st.subheader("🔍 Buscador")
    busq = st.text_input("Código", placeholder="Buscar...", key="bus_main").upper().strip()
    if busq:
        res = {k: v for k, v in inv.items() if busq in k}
        for k, v in res.items(): st.success(f"✅ {v['deposito']} | {v['marca']} | {k.split('_')[-1]} | STOCK: {v['stock']}")
    st.divider()
    d_v = st.selectbox("Bodega:", config["depositos"], key="sel_dep_main")
    
    # PROTECCIÓN DE PESTAÑAS
    marcas_list = config["marcas"] if config["marcas"] else ["GENERAL"]
    tabs_main = st.tabs(marcas_list)
    for i, m in enumerate(marcas_list):
        with tabs_main[i]:
            items = {k: v for k, v in inv.items() if v['marca']==m and v['deposito']==d_v}
            for kid, info in sorted(items.items()): st.write(f"**{kid.split('_')[-1]}**: {info['stock']} cajas")

else:
    # --- PANEL EDICIÓN ---
    st.header("🛠️ Panel Edición")
    bus_ed = st.text_input("🎯 Buscar código rápido:", key="bus_edit_panel").upper().strip()
    if bus_ed:
        for k, v in {k: v for k, v in inv.items() if bus_ed in k}.items(): mostrar_tarjeta(k, v, "rap")
    st.divider()
    
    dep_p = st.selectbox("Bodega de trabajo:", config["depositos"], key="sel_dep_edit")
    
    # PROTECCIÓN DE PESTAÑAS EN EDICIÓN
    marcas_edit = config["marcas"] if config["marcas"] else ["GENERAL"]
    tabs_edit = st.tabs(marcas_edit)
    for i, m_p in enumerate(marcas_edit):
        with tabs_edit[i]:
            items_p = {k: v for k, v in inv.items() if v['marca']==m_p and v['deposito']==dep_p}
            for k, v in sorted(items_p.items()): mostrar_tarjeta(k, v, f"panel_{i}")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔐 Acceso")
    if not st.session_state.edit_mode:
        u = st.selectbox("Usuario", list(config["usuarios"].keys()))
        p = st.text_input("Clave", type="password")
        if st.button("🔓 Entrar"):
            if config["usuarios"].get(u) == p:
                st.session_state.edit_mode, st.session_state.usuario_actual = True, u
                st.rerun()
    else:
        st.write(f"👤 **{st.session_state.usuario_actual}**")
        if st.button("⚙️ PANEL" if not st.session_state.modo_panel else "🏠 INICIO"):
            st.session_state.modo_panel = not st.session_state.modo_panel
            st.rerun()

        if st.session_state.usuario_actual.upper() == "ADMIN":
            if st.button("📜 HISTORIAL"): st.session_state.ver_historial=True; st.rerun()
            with st.expander("👤 Usuarios"):
                nu_nom = st.text_input("Nuevo Usuario").upper().strip()
                nu_cla = st.text_input("Clave", type="password", key="c_new")
                if st.button("🚀 Crear"):
                    if nu_nom: guardar_cambio_google(sh, "CONFIG", "MANAGE_USER", [nu_nom, nu_cla, "CREAR"]); st.session_state.clear(); st.rerun()
                st.divider()
                u_sel = st.selectbox("Editar:", [u for u in config["usuarios"].keys() if u != "ADMIN"])
                new_p = st.text_input("Nueva Clave", type="password", key="c_mod")
                c1, c2 = st.columns(2)
                if c1.button("💾 Mod"): 
                    guardar_cambio_google(sh, "CONFIG", "MANAGE_USER", [u_sel, new_p, "MODIFICAR"]); st.session_state.clear(); st.rerun()
                if c2.button("🗑️ Del"): 
                    guardar_cambio_google(sh, "CONFIG", "MANAGE_USER", [u_sel, "", "ELIMINAR"]); st.session_state.clear(); st.rerun()

            with st.expander("🏘️ Bodegas"):
                b_sel = st.selectbox("Bodega:", config["depositos"], key="b_ed")
                nuevo_nb = st.text_input("Nuevo nombre:").upper().strip()
                if st.button("📝 Renombrar"):
                    if nuevo_nb: guardar_cambio_google(sh, "CONFIG", "RENAME_CONFIG", [b_sel, nuevo_nb, 3]); st.session_state.clear(); st.rerun()
                st.divider()
                nb = st.text_input("Añadir Bodega").upper().strip()
                if st.button("➕ Añadir Bodega"):
                    if nb: guardar_cambio_google(sh, "CONFIG", "ADD_CONFIG", [nb, 3]); st.session_state.clear(); st.rerun()

            with st.expander("🏷️ Marcas"):
                m_sel = st.selectbox("Marca:", config["marcas"], key="m_ed")
                if st.button("🗑️ Borrar Marca"):
                    guardar_cambio_google(sh, "CONFIG", "DEL_CONFIG", [m_sel, 4]); st.session_state.clear(); st.rerun()
                st.divider()
                nm = st.text_input("Añadir Marca").upper().strip()
                if st.button("➕ Añadir Marca"):
                    if nm: guardar_cambio_google(sh, "CONFIG", "ADD_CONFIG", [nm, 4]); st.session_state.clear(); st.rerun()

        with st.expander("🆕 Nuevo Código"):
            nma = st.selectbox("Marca", config["marcas"])
            nco = st.text_input("Código").upper().strip()
            nbo = st.selectbox("Bodega", config["depositos"])
            if st.button("💾 Crear Item"):
                if nco: guardar_cambio_google(sh, "INVENTARIO", "NUEVO_ITEM", [nma, nbo, nco, 0]); st.session_state.clear(); st.rerun()

        if st.button("🔒 Salir"): st.session_state.edit_mode = False; st.rerun()
