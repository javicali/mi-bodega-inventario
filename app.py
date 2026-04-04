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
    except:
        return None

def cargar_datos_google():
    # Valores por defecto para que NUNCA desaparezcan los botones
    def_config = {"usuarios": {"ADMIN": "123"}, "depositos": ["PRINCIPAL"], "marcas": ["GENERAL"]}
    try:
        sh = conectar_google()
        if not sh: return {}, def_config, [], None
        
        # Cargar Inventario
        ws_inv = sh.worksheet("INVENTARIO")
        datos_inv = ws_inv.get_all_records()
        inv = {f"{r['DEPOSITO']}_{r['CODIGO']}": {"marca": r['MARCA'], "deposito": r['DEPOSITO'], "stock": int(r['STOCK'])} 
               for r in datos_inv if str(r.get('CODIGO')).strip()}
        
        # Cargar Configuración (Usuarios, Bodegas, Marcas)
        ws_conf = sh.worksheet("CONFIG")
        df_conf = pd.DataFrame(ws_conf.get_all_records())
        
        # Limpieza de datos: quitar vacíos y duplicados
        list_users = {str(r['USUARIO']).strip(): str(r['CLAVE']).strip() for _, r in df_conf.iterrows() if str(r.get('USUARIO')).strip()}
        list_depos = [x for x in df_conf['DEPOSITOS'].unique() if str(x).strip()] if 'DEPOSITOS' in df_conf else []
        list_marcas = [x for x in df_conf['MARCAS'].unique() if str(x).strip()] if 'MARCAS' in df_conf else []

        # Si las listas están vacías en el Excel, poner valores por defecto
        config = {
            "usuarios": list_users if list_users else def_config["usuarios"],
            "depositos": list_depos if list_depos else def_config["depositos"],
            "marcas": list_marcas if list_marcas else def_config["marcas"]
        }
        
        # Cargar Logs
        ws_log = sh.worksheet("LOGS")
        logs_data = ws_log.get_all_records()
        
        return inv, config, logs_data, sh
    except Exception as e:
        return {}, def_config, [], None

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
        elif accion == "NUEVO_ITEM":
            ws.append_row(datos)
        elif accion == "ADD_CONFIG":
            col = datos[1] # 3 depo, 4 marcas
            # Buscar primera fila vacía en la columna específica
            col_vals = ws.col_values(col)
            ws.update_cell(len(col_vals) + 1, col, datos[0])
        elif accion == "MANAGE_USER":
            if datos[2] == "CREAR": ws.append_row([datos[0], datos[1]])
            elif datos[2] == "ELIMINAR":
                celda = ws.find(datos[0])
                if celda and celda.col == 1: ws.delete_rows(celda.row)
    except:
        st.error("⚠️ Error de conexión con Google Sheets")

# --- 2. INICIALIZACIÓN ---
st.set_page_config(page_title="Bodega Pro Ultra", layout="wide")

if 'data_loaded' not in st.session_state:
    st.session_state.inv, st.session_state.config, st.session_state.logs, st.session_state.sh = cargar_datos_google()
    st.session_state.data_loaded = True

inv, config, logs, sh = st.session_state.inv, st.session_state.config, st.session_state.logs, st.session_state.sh

if 'edit_mode' not in st.session_state: st.session_state.edit_mode = False
if 'modo_panel' not in st.session_state: st.session_state.modo_panel = False
if 'ver_historial' not in st.session_state: st.session_state.ver_historial = False

# --- FUNCIONES DE INTERFAZ ---
def mostrar_tarjeta_edicion(k, v, sufijo):
    with st.container(border=True):
        c1, c2, c3 = st.columns([2, 1, 2.5])
        c1.markdown(f"**{k.split('_')[-1]}**\n<small>{v['marca']} | {v['deposito']}</small>", unsafe_allow_html=True)
        c2.write(f"📦 {v['stock']}")
        with c3:
            cant = st.number_input("Cant", min_value=1, value=1, key=f"n_{sufijo}_{k}", label_visibility="collapsed")
            b1, b2 = st.columns(2)
            if b1.button("➕", key=f"add_{sufijo}_{k}"):
                v['stock'] += cant
                guardar_cambio_google(sh, "INVENTARIO", "UPDATE_STOCK", [k, v['stock']])
                guardar_cambio_google(sh, "LOGS", "ADD_LOG", [st.session_state.usuario_actual, "ENTRADA", f"Sumó {cant} a {k}"])
                st.rerun()
            if b2.button("➖", key=f"sub_{sufijo}_{k}", disabled=v['stock']<cant):
                v['stock'] -= cant
                guardar_cambio_google(sh, "INVENTARIO", "UPDATE_STOCK", [k, v['stock']])
                guardar_cambio_google(sh, "LOGS", "ADD_LOG", [st.session_state.usuario_actual, "SALIDA", f"Restó {cant} a {k}"])
                st.rerun()

# --- 3. CUERPO PRINCIPAL ---
st.title("🏢 Sistema de Bodega")

if st.session_state.ver_historial:
    st.header("📜 Historial de Actividad")
    if st.button("⬅️ Volver al Inicio"):
        st.session_state.ver_historial = False
        st.rerun()
    df_l = pd.DataFrame(logs)
    if not df_l.empty: st.dataframe(df_l.iloc[::-1], use_container_width=True)
    else: st.info("No hay movimientos registrados.")

elif not st.session_state.modo_panel:
    # --- VISTA CONSULTA ---
    st.subheader("🔍 Buscador de Códigos")
    c_bus, c_btn = st.columns([3, 1])
    with c_bus:
        busq = st.text_input("Código", placeholder="Escriba aquí...", label_visibility="collapsed").upper().strip()
    with c_btn:
        st.button("🔎 BUSCAR")

    if busq:
        res = {k: v for k, v in inv.items() if busq in k}
        for k, v in res.items():
            if v['stock'] > 0: st.success(f"✅ {v['deposito']}: {v['marca']} - {k.split('_')[-1]} | STOCK: {v['stock']}")
            else: st.error(f"🚨 AGOTADO en {v['deposito']}: {k.split('_')[-1]}")

    st.divider()
    # AQUÍ ESTÁN LOS BOTONES QUE DESAPARECIERON
    st.subheader("📦 Stock por Ubicación")
    d_v = st.selectbox("📍 Seleccione Bodega:", config["depositos"])
    tbs = st.tabs(config["marcas"])
    for i, m in enumerate(config["marcas"]):
        with tbs[i]:
            items = {k: v for k, v in inv.items() if v['marca']==m and v['deposito']==d_v}
            if items:
                for kid, info in sorted(items.items()):
                    st.write(f"**{kid.split('_')[-1]}**: {info['stock']} unidades")
            else: st.write("_Sin registros en esta marca._")

else:
    # --- PANEL DE EDICIÓN ---
    st.header("🛠️ Panel de Edición")
    bus_ed = st.text_input("🎯 Buscar para editar rápido:").upper().strip()
    if bus_ed:
        res_ed = {k: v for k, v in inv.items() if bus_ed in k}
        for k, v in res_ed.items(): mostrar_tarjeta_edicion(k, v, "rap")
    
    st.divider()
    dep_p = st.selectbox("📍 Bodega de trabajo:", config["depositos"])
    tabs_p = st.tabs(config["marcas"])
    for i, m_p in enumerate(config["marcas"]):
        with tabs_p[i]:
            it_p = {k: v for k, v in inv.items() if v['marca']==m_p and v['deposito']==dep_p}
            for k, v in sorted(it_p.items()): mostrar_tarjeta_edicion(k, v, f"tab_{i}")

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
        st.write(f"👤 Usuario: **{st.session_state.usuario_actual}**")
        
        if st.button("🏠 VISTA INICIO" if st.session_state.modo_panel else "⚙️ PANEL CONTROL"):
            st.session_state.modo_panel = not st.session_state.modo_panel
            st.session_state.ver_historial = False
            st.rerun()

        if st.session_state.usuario_actual.upper() == "ADMIN":
            if st.button("📜 VER HISTORIAL"):
                st.session_state.ver_historial = True
                st.session_state.modo_panel = False
                st.rerun()

        with st.expander("👤 Gestión Usuarios"):
            un = st.text_input("Nombre").upper().strip()
            up = st.text_input("Clave", type="password", key="newpass")
            if st.button("💾 Guardar Usuario"):
                op = "MODIFICAR" if un in config["usuarios"] else "CREAR"
                guardar_cambio_google(sh, "CONFIG", "MANAGE_USER", [un, up, op])
                st.session_state.clear(); st.rerun()

        with st.expander("🆕 Nuevo Código"):
            nm = st.selectbox("Marca", config["marcas"], key="nma")
            nc = st.text_input("Código Item").upper().strip()
            nd = st.selectbox("Bodega", config["depositos"], key="nbo")
            if st.button("💾 Crear Producto"):
                if nc:
                    guardar_cambio_google(sh, "INVENTARIO", "NUEVO_ITEM", [nm, nd, nc, 0])
                    st.session_state.clear(); st.rerun()

        with st.expander("🏘️ Gestionar Marcas/Bodegas"):
            nueva_m = st.text_input("Añadir Marca").upper().strip()
            if st.button("➕ Añadir Marca"):
                if nueva_m: guardar_cambio_google(sh, "CONFIG", "ADD_CONFIG", [nueva_m, 4]); st.session_state.clear(); st.rerun()
            st.divider()
            nueva_b = st.text_input("Añadir Bodega").upper().strip()
            if st.button("➕ Añadir Bodega"):
                if nueva_b: guardar_cambio_google(sh, "CONFIG", "ADD_CONFIG", [nueva_b, 3]); st.session_state.clear(); st.rerun()

        if st.button("🔒 Salir"):
            st.session_state.edit_mode = False; st.session_state.modo_panel = False; st.rerun()
