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

def generar_excel_reporte(datos_inv):
    reporte = []
    for k, v in datos_inv.items():
        reporte.append({
            "BODEGA": v["deposito"], "MARCA": v["marca"], "CÓDIGO": k.split("_")[-1],
            "STOCK ACTUAL": v["stock"], "CONTEO FÍSICO": "", "DIFERENCIA": ""
        })
    df = pd.DataFrame(reporte).sort_values(by=["BODEGA", "MARCA"])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Inventario')
    return output.getvalue()

def guardar_cambio_google(sh, tab, accion, datos):
    try:
        ws = sh.worksheet(tab)
        if accion == "UPDATE_STOCK":
            celda = ws.find(str(datos[0].split("_")[-1]))
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

def txt_cajas(n): return f"{n} caja" if n == 1 else f"{n} cajas"

# --- 2. INICIALIZACIÓN ---
st.set_page_config(page_title="Bodega Pro Ultra", layout="wide")

if 'reset_pub' not in st.session_state: st.session_state.reset_pub = 0
if 'reset_pan' not in st.session_state: st.session_state.reset_pan = 0

def recargar():
    st.session_state.inv, st.session_state.config, st.session_state.logs, st.session_state.sh = cargar_datos_google()

if 'data_loaded' not in st.session_state:
    recargar()
    st.session_state.data_loaded = True

inv, config, logs, sh = st.session_state.inv, st.session_state.config, st.session_state.logs, st.session_state.sh

# --- DIALOGOS ---
@st.dialog("Confirmar Movimiento")
def confirmar_mov(k, v, cant, op):
    st.warning(f"¿Confirmas {op} {txt_cajas(cant)} a {k.split('_')[-1]}?")
    c1, c2 = st.columns(2)
    if c1.button("SÍ, GUARDAR", use_container_width=True):
        nuevo = v['stock'] + cant if op == 'SUMAR' else v['stock'] - cant
        guardar_cambio_google(sh, "INVENTARIO", "UPDATE_STOCK", [k, nuevo])
        guardar_cambio_google(sh, "LOGS", "ADD_LOG", [st.session_state.usuario_actual, op, f"{txt_cajas(cant)} de {k}"])
        recargar(); st.rerun()
    if c2.button("CANCELAR", use_container_width=True): st.rerun()

def mostrar_tarjeta(k, v, suf):
    with st.container(border=True):
        c1, c2, c3 = st.columns([2, 1, 3])
        c1.markdown(f"**{k.split('_')[-1]}**\n<small>{v['marca']} | {v['deposito']}</small>", unsafe_allow_html=True)
        c2.write(f"📦 {txt_cajas(v['stock'])}")
        with c3:
            cant = st.number_input("n", min_value=1, key=f"n_{suf}_{k}", label_visibility="collapsed")
            cols_btn = st.columns(2)
            if cols_btn[0].button("➕", key=f"btn_add_{suf}_{k}"): confirmar_mov(k, v, cant, "SUMAR")
            if cols_btn[1].button("➖", key=f"btn_sub_{suf}_{k}", disabled=v['stock']<cant): confirmar_mov(k, v, cant, "RESTAR")

# --- 3. INTERFAZ PRINCIPAL ---
st.title("🏢 Bodega Central")

if st.session_state.get('ver_historial', False):
    st.header("📜 Historial")
    if st.button("⬅️ Volver"): st.session_state.ver_historial = False; st.rerun()
    st.dataframe(pd.DataFrame(logs).iloc[::-1], use_container_width=True)

elif not st.session_state.get('modo_panel', False):
    # --- CONSULTA PÚBLICA ---
    st.subheader("🔍 Consulta de Stock")
    col_input, col_lupa = st.columns([4, 1])
    with col_input:
        bus_p = st.text_input("Código:", key=f"in_pub_{st.session_state.reset_pub}", placeholder="Ej: 212", label_visibility="collapsed").upper().strip()
    with col_lupa:
        btn_lupa = st.button("🔍 OK", use_container_width=True)

    if bus_p or btn_lupa:
        encontrados = {k: v for k, v in inv.items() if str(k.split('_')[-1]) == bus_p}
        if encontrados:
            for k, v in encontrados.items():
                color = "green" if v['stock'] > 0 else "red"
                st.markdown(f'<div style="border:2px solid {color};padding:15px;border-radius:10px;margin-bottom:10px;"><h3>📦 {k.split("_")[-1]}</h3><p>Bodega: {v["deposito"]} | Marca: {v["marca"]}</p><h2 style="color:{color};">Stock: {txt_cajas(v["stock"])}</h2></div>', unsafe_allow_html=True)
            if st.button("🗑️ Limpiar Búsqueda", use_container_width=True):
                st.session_state.reset_pub += 1; st.rerun()
        elif bus_p:
            st.error(f"❌ El código '{bus_p}' no existe.")
            if st.button("🔄 Borrar"): st.session_state.reset_pub += 1; st.rerun()

    st.divider()
    if st.button("📦 VER LISTADO POR BODEGA", use_container_width=True):
        st.session_state.ver_menu_marcas = not st.session_state.get('ver_menu_marcas', False); st.rerun()
    if st.session_state.get('ver_menu_marcas', False):
        d_v = st.selectbox("Selecciona la Bodega:", config["depositos"])
        for kid, info in sorted({k: v for k, v in inv.items() if v['deposito'] == d_v and v['stock'] > 0}.items(), key=lambda x: x[1]['marca']):
            st.write(f"🔹 **{kid.split('_')[-1]}** | {info['marca']} | **{txt_cajas(info['stock'])}**")

else:
    # --- PANEL DE TRABAJO ---
    st.header("🛠️ Panel de Trabajo")
    bus_e = st.text_input("🎯 Código exacto:", key=f"in_pan_{st.session_state.reset_pan}").upper().strip()
    if bus_e:
        encontrados_ed = {k: v for k, v in inv.items() if str(k.split('_')[-1]) == bus_e}
        if encontrados_ed:
            for k, v in encontrados_ed.items(): mostrar_tarjeta(k, v, "rap")
            if st.button("🗑️ Limpiar Filtro"): st.session_state.reset_pan += 1; st.rerun()
        else:
            st.warning(f"⚠️ No existe el código '{bus_e}'")
            if st.button("🔄 Borrar"): st.session_state.reset_pan += 1; st.rerun()

    st.divider()
    dep_p = st.selectbox("Bodega:", config["depositos"], key="sel_dep_edit")
    tabs_e = st.tabs(config["marcas"] if config["marcas"] else ["GENERAL"])
    for i, m_p in enumerate(config["marcas"]):
        with tabs_e[i]:
            for k, v in sorted({k: v for k, v in inv.items() if v['marca']==m_p and v['deposito']==dep_p}.items()):
                mostrar_tarjeta(k, v, f"pan_{i}")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔐 Acceso")
    if not st.session_state.get('edit_mode', False):
        u = st.selectbox("Usuario", list(config["usuarios"].keys()))
        p = st.text_input("Clave", type="password")
        if st.button("🔓 Entrar"):
            if config["usuarios"].get(u) == p:
                st.session_state.edit_mode, st.session_state.usuario_actual = True, u
                st.rerun()
            else: st.error("Clave incorrecta")
    else:
        st.write(f"👤 **{st.session_state.usuario_actual}**")
        if st.button("⚙️ PANEL" if not st.session_state.get('modo_panel', False) else "🏠 INICIO", use_container_width=True):
            st.session_state.modo_panel = not st.session_state.get('modo_panel', False); st.rerun()
        
        with st.expander("🆕 Nuevo Código"):
            nma, nco, nbo = st.selectbox("Marca", config["marcas"]), st.text_input("Código").upper().strip(), st.selectbox("Bodega", config["depositos"])
            if st.button("💾 Crear"):
                if nco: guardar_cambio_google(sh, "INVENTARIO", "NUEVO_ITEM", [nma, nbo, nco, 0]); recargar(); st.rerun()

        if st.session_state.usuario_actual.upper() == "ADMIN":
            with st.expander("👤 Usuarios"):
                un, uc = st.text_input("Nombre").upper().strip(), st.text_input("Clave admin", type="password")
                if st.button("🚀 Crear Usuario"): guardar_cambio_google(sh, "CONFIG", "MANAGE_USER", [un, uc, "CREAR"]); recargar(); st.rerun()
            with st.expander("🏷️ Marcas"):
                m_s = st.selectbox("Marca:", config["marcas"])
                if st.button("🗑️ Borrar Marca"): guardar_cambio_google(sh, "CONFIG", "DEL_CONFIG", [m_s, 4]); recargar(); st.rerun()
                nm = st.text_input("Añadir Marca").upper().strip()
                if st.button("➕ Añadir Marca"): guardar_cambio_google(sh, "CONFIG", "ADD_CONFIG", [nm, 4]); recargar(); st.rerun()
            with st.expander("🏘️ Bodegas"):
                b_s = st.selectbox("Bodega:", config["depositos"])
                n_nb = st.text_input("Nuevo nombre:").upper().strip()
                if st.button("📝 Renombrar Bodega"): guardar_cambio_google(sh, "CONFIG", "RENAME_CONFIG", [b_s, n_nb, 3]); recargar(); st.rerun()

            if st.button("📜 HISTORIAL", use_container_width=True): st.session_state.ver_historial = True; st.rerun()
            st.divider()
            st.download_button(label="📊 REPORTE CONTROL FÍSICO", data=generar_excel_reporte(inv), file_name=f"Reporte_{datetime.now().strftime('%d_%m')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

        if st.button("🔒 Salir", use_container_width=True): 
            st.session_state.edit_mode = False; st.session_state.usuario_actual = None; st.session_state.modo_panel = False; st.rerun()
