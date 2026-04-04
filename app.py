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
            if celda: ws.update_cell(celda.row, 4, datos[1])
        elif accion == "ADD_LOG":
            hora = (datetime.now() - timedelta(hours=4)).strftime("%d/%m/%Y %H:%M")
            ws.append_row([hora] + datos)
        elif accion == "NUEVO_ITEM": ws.append_row(datos)
        elif accion == "DELETE_ITEM":
            celda = ws.find(datos[0].split("_")[-1])
            if celda: ws.delete_rows(celda.row)
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

def recargar():
    st.session_state.inv, st.session_state.config, st.session_state.logs, st.session_state.sh = cargar_datos_google()

if 'data_loaded' not in st.session_state:
    recargar()
    st.session_state.data_loaded = True

inv, config, logs, sh = st.session_state.inv, st.session_state.config, st.session_state.logs, st.session_state.sh

if 'edit_mode' not in st.session_state: st.session_state.edit_mode = False
if 'modo_panel' not in st.session_state: st.session_state.modo_panel = False
if 'ver_historial' not in st.session_state: st.session_state.ver_historial = False

# --- DIALOGOS ---
@st.dialog("Detalle del Artículo")
def mostrar_detalle_dialogo(k, v):
    st.write(f"### 📦 {k.split('_')[-1]}")
    st.divider()
    c1, c2 = st.columns(2)
    c1.metric("Stock Actual", f"{v['stock']} cajas")
    c1.write(f"**Marca:** {v['marca']}")
    c1.write(f"**Bodega:** {v['deposito']}")
    
    if v['stock'] == 0:
        st.error("🚨 ESTE ARTÍCULO NO TIENE STOCK")
    else:
        st.success("✅ Artículo disponible")
    
    if st.button("Cerrar"): st.rerun()

@st.dialog("Confirmar Movimiento")
def confirmar_mov(k, v, cant, op):
    st.warning(f"¿Confirmas {op} {cant} cajas a {k.split('_')[-1]}?")
    c1, c2 = st.columns(2)
    if c1.button("SÍ, GUARDAR", use_container_width=True):
        nuevo = v['stock'] + cant if op == 'SUMAR' else v['stock'] - cant
        guardar_cambio_google(sh, "INVENTARIO", "UPDATE_STOCK", [k, nuevo])
        guardar_cambio_google(sh, "LOGS", "ADD_LOG", [st.session_state.usuario_actual, op, f"{cant} cajas de {k}"])
        recargar()
        st.rerun()
    if c2.button("CANCELAR", use_container_width=True): st.rerun()

@st.dialog("Eliminar Artículo")
def confirmar_borrado_item(k):
    st.error(f"⚠️ **¿BORRAR?**")
    c1, c2 = st.columns(2)
    if c1.button("🔥 ELIMINAR", use_container_width=True):
        guardar_cambio_google(sh, "INVENTARIO", "DELETE_ITEM", [k])
        guardar_cambio_google(sh, "LOGS", "ADD_LOG", [st.session_state.usuario_actual, "BORRADO", f"Eliminó {k}"])
        recargar()
        st.rerun()
    if c2.button("VOLVER", use_container_width=True): st.rerun()

# --- TARJETA ---
def mostrar_tarjeta(k, v, suf, permite_borrar=False):
    with st.container(border=True):
        c1, c2, c3 = st.columns([2, 1, 3])
        c1.markdown(f"**{k.split('_')[-1]}**\n<small>{v['marca']} | {v['deposito']}</small>", unsafe_allow_html=True)
        c2.write(f"📦 {v['stock']}")
        with c3:
            cant = st.number_input("n", min_value=1, key=f"n_{suf}_{k}", label_visibility="collapsed")
            cols_btn = st.columns([1, 1, 1]) if permite_borrar else st.columns(2)
            if cols_btn[0].button("➕", key=f"btn_add_{suf}_{k}"): confirmar_mov(k, v, cant, "SUMAR")
            if cols_btn[1].button("➖", key=f"btn_sub_{suf}_{k}", disabled=v['stock']<cant): confirmar_mov(k, v, cant, "RESTAR")
            if permite_borrar:
                if cols_btn[2].button("🗑️", key=f"btn_del_{suf}_{k}"): confirmar_borrado_item(k)

# --- 3. INTERFAZ ---
st.title("🏢 Sistema de Bodega")

if st.session_state.ver_historial:
    st.header("📜 Historial")
    if st.button("⬅️ Volver"): st.session_state.ver_historial = False; st.rerun()
    st.dataframe(pd.DataFrame(logs).iloc[::-1], use_container_width=True)

elif not st.session_state.modo_panel:
    # --- VISTA PRINCIPAL (LIMPIA) ---
    st.subheader("🔍 Consulta Rápida")
    busq = st.text_input("Buscar código...", key="bus_main").upper().strip()
    
    st.divider()
    d_v = st.selectbox("Bodega:", config["depositos"], key="sel_dep_main")
    mlist = config["marcas"] if config["marcas"] else ["GENERAL"]
    tabs_m = st.tabs(mlist)
    
    for i, m in enumerate(mlist):
        with tabs_m[i]:
            items = {k: v for k, v in inv.items() if v['marca']==m and v['deposito']==d_v}
            if busq:
                items = {k: v for k, v in items.items() if busq in k}
            
            for kid, info in sorted(items.items()):
                c_nom, c_ver = st.columns([4, 1])
                # Mostrar solo el nombre
                prefix = "✅" if info['stock'] > 0 else "❌"
                c_nom.write(f"{prefix} **{kid.split('_')[-1]}**")
                # Botón para ver detalle
                if c_ver.button("👁️ Ver", key=f"ver_{kid}"):
                    mostrar_detalle_dialogo(kid, info)

else:
    # --- PANEL DE EDICIÓN (CON TARJETAS) ---
    st.header("🛠️ Panel Edición")
    bus_ed = st.text_input("🎯 Buscar código rápido:", key="bus_edit").upper().strip()
    if bus_ed:
        for k, v in {k: v for k, v in inv.items() if bus_ed in k}.items(): 
            mostrar_tarjeta(k, v, "rap", permite_borrar=(v['stock']==0))
    st.divider()
    dep_p = st.selectbox("Bodega de trabajo:", config["depositos"], key="sel_dep_edit")
    mlist_e = config["marcas"] if config["marcas"] else ["GENERAL"]
    tabs_e = st.tabs(mlist_e)
    for i, m_p in enumerate(mlist_e):
        with tabs_e[i]:
            it_p = {k: v for k, v in inv.items() if v['marca']==m_p and v['deposito']==dep_p}
            c_s_p = {k: v for k, v in it_p.items() if v['stock'] > 0}
            s_s_p = {k: v for k, v in it_p.items() if v['stock'] == 0}
            for k, v in sorted(c_s_p.items()): mostrar_tarjeta(k, v, f"pan_{i}")
            if s_s_p:
                with st.expander("🚫 ARTÍCULOS SIN STOCK"):
                    for k, v in sorted(s_s_p.items()): mostrar_tarjeta(k, v, f"sin_{i}", permite_borrar=True)

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔐 Acceso")
    if not st.session_state.edit_mode:
        u = st.selectbox("Usuario", list(config["usuarios"].keys()))
        p = st.text_input("Clave", type="password")
        if st.button("🔓 Entrar", key="btn_login"):
            if config["usuarios"].get(u) == p:
                st.session_state.edit_mode, st.session_state.usuario_actual = True, u
                st.rerun()
    else:
        st.write(f"👤 **{st.session_state.usuario_actual}**")
        
        if st.button("⚙️ PANEL" if not st.session_state.modo_panel else "🏠 INICIO", key="btn_toggle_panel", use_container_width=True):
            st.session_state.modo_panel = not st.session_state.modo_panel
            st.rerun()

        with st.expander("🆕 Crear Nuevo Código"):
            nma = st.selectbox("Marca", config["marcas"], key="new_item_m")
            nco = st.text_input("Código", key="new_item_c").upper().strip()
            nbo = st.selectbox("Bodega", config["depositos"], key="new_item_b")
            if st.button("💾 Crear Item", key="btn_crear_item"):
                if nco: 
                    guardar_cambio_google(sh, "INVENTARIO", "NUEVO_ITEM", [nma, nbo, nco, 0])
                    recargar()
                    st.rerun()

        if st.session_state.usuario_actual.upper() == "ADMIN":
            with st.expander("👤 Gestión de Usuarios"):
                nu_n = st.text_input("Nombre Nuevo").upper().strip()
                nu_c = st.text_input("Clave Nueva", type="password", key="new_u_key")
                if st.button("🚀 Crear Usuario", key="btn_crear_u"):
                    if nu_n: 
                        guardar_cambio_google(sh, "CONFIG", "MANAGE_USER", [nu_n, nu_c, "CREAR"])
                        recargar()
                        st.rerun()
                st.divider()
                u_s = st.selectbox("Seleccionar:", [u for u in config["usuarios"].keys() if u != "ADMIN"], key="u_sel_edit")
                n_p = st.text_input("Nueva Clave", type="password", key="mod_u_key")
                c1, c2 = st.columns(2)
                if c1.button("💾 Modificar", key="btn_mod_u"):
                    guardar_cambio_google(sh, "CONFIG", "MANAGE_USER", [u_s, n_p, "MODIFICAR"])
                    recargar()
                    st.rerun()
                if c2.button("🗑️ Eliminar", key="btn_del_u"):
                    guardar_cambio_google(sh, "CONFIG", "MANAGE_USER", [u_s, "", "ELIMINAR"])
                    recargar()
                    st.rerun()

            with st.expander("🏷️ Gestión de Marcas"):
                m_s = st.selectbox("Marca:", config["marcas"], key="m_edit_sel")
                if st.button("🗑️ Borrar Marca", key="btn_del_m"):
                    guardar_cambio_google(sh, "CONFIG", "DEL_CONFIG", [m_s, 4])
                    recargar()
                    st.rerun()
                st.divider()
                nm = st.text_input("Añadir Marca", key="m_add_input").upper().strip()
                if st.button("➕ Añadir Marca", key="btn_add_m"):
                    if nm: 
                        guardar_cambio_google(sh, "CONFIG", "ADD_CONFIG", [nm, 4])
                        recargar()
                        st.rerun()

            with st.expander("🏘️ Gestión de Bodegas"):
                b_s = st.selectbox("Bodega:", config["depositos"], key="b_edit_sel")
                n_nb = st.text_input("Nuevo nombre:", key="b_rename_input").upper().strip()
                if st.button("📝 Renombrar", key="btn_ren_b"):
                    if n_nb: 
                        guardar_cambio_google(sh, "CONFIG", "RENAME_CONFIG", [b_s, n_nb, 3])
                        recargar()
                        st.rerun()
                st.divider()
                nb = st.text_input("Añadir Bodega", key="b_add_input").upper().strip()
                if st.button("➕ Añadir Bodega", key="btn_add_b"):
                    if nb: 
                        guardar_cambio_google(sh, "CONFIG", "ADD_CONFIG", [nb, 3])
                        recargar()
                        st.rerun()

            if st.button("📜 HISTORIAL", key="btn_hist", use_container_width=True): 
                st.session_state.ver_historial = True
                st.rerun()

        st.divider()
        if st.button("🔒 Salir", key="btn_logout", use_container_width=True): 
            st.session_state.edit_mode = False
            st.session_state.usuario_actual = None
            st.rerun()
