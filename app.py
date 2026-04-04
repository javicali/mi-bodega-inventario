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
    except Exception as e:
        st.error(f"❌ Error de conexión: {e}")
        return None

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
            codigo_puro = str(datos[0].split("_")[-1]).strip()
            celda = ws.find(codigo_puro, in_column=3)
            if celda:
                ws.update_cell(celda.row, 4, int(datos[1]))
                return True
            else:
                st.error(f"❌ El código '{codigo_puro}' no existe en el Excel.")
                return False
        elif accion == "ADD_LOG":
            hora = (datetime.now() - timedelta(hours=4)).strftime("%d/%m/%Y %H:%M")
            ws.append_row([hora] + datos)
            return True
        elif accion == "NUEVO_ITEM":
            ws.append_row(datos)
            st.toast(f"✅ Código '{datos[2]}' creado", icon="🆕")
            return True
        elif accion == "ADD_CONFIG":
            col_vals = ws.col_values(datos[1])
            ws.update_cell(len(col_vals) + 1, datos[1], datos[0])
            st.toast(f"✅ Añadido: {datos[0]}", icon="➕")
            return True
        elif accion == "DEL_CONFIG":
            celda = ws.find(datos[0])
            if celda and celda.col == datos[1]: 
                ws.update_cell(celda.row, datos[1], "")
                st.toast(f"🗑️ Eliminado correctamente", icon="🔥")
                return True
        elif accion == "RENAME_CONFIG":
            celda = ws.find(datos[0])
            if celda and celda.col == datos[2]: 
                ws.update_cell(celda.row, datos[2], datos[1])
                st.toast(f"📝 Renombrado a: {datos[1]}", icon="🏠")
                return True
        elif accion == "MANAGE_USER":
            if datos[2] == "CREAR": 
                ws.append_row([datos[0], datos[1]], value_input_option='RAW')
                st.toast(f"👤 Usuario {datos[0]} creado", icon="🚀")
            elif datos[2] == "ELIMINAR":
                celda = ws.find(datos[0])
                if celda and celda.col == 1: 
                    ws.delete_rows(celda.row)
                    st.toast(f"👤 Usuario eliminado", icon="🗑️")
            return True
    except Exception as e:
        st.error(f"⚠️ Error: {e}")
        return False

def txt_cajas(n):
    return f"{n} caja" if n == 1 else f"{n} cajas"

# --- 2. INICIALIZACIÓN ---
st.set_page_config(page_title="Bodega Sistema", layout="wide")

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
        nuevo_val = v['stock'] + cant if op == 'SUMAR' else v['stock'] - cant
        if guardar_cambio_google(sh, "INVENTARIO", "UPDATE_STOCK", [k, nuevo_val]):
            guardar_cambio_google(sh, "LOGS", "ADD_LOG", [st.session_state.usuario_actual, op, f"{txt_cajas(cant)} de {k}"])
            st.toast(f"📦 Stock actualizado", icon="✅")
            recargar()
            st.rerun()
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
            if cols_btn[1].button("➖", key=f"btn_sub_{suf}_{k}", disabled=v['stock'] < cant): confirmar_mov(k, v, cant, "RESTAR")

# --- 3. INTERFAZ PRINCIPAL ---
st.title("🏢 Bodega Central")

if st.session_state.get('ver_historial'):
    st.header("📜 Historial")
    if st.button("⬅️ Volver"): st.session_state.ver_historial = False; st.rerun()
    st.dataframe(pd.DataFrame(logs).iloc[::-1], use_container_width=True)

elif not st.session_state.get('modo_panel'):
    # --- MODO INICIO (BUSCADOR PÚBLICO) ---
    st.subheader("🔍 Buscar Producto")
    c_input, c_ok = st.columns([4, 1])
    codigo_buscado = c_input.text_input("Ingresa el código:", placeholder="Escribe aquí...", label_visibility="collapsed").upper().strip()
    
    if c_ok.button("🔍 OK", use_container_width=True):
        if codigo_buscado:
            encontrados = {k: v for k, v in inv.items() if codigo_buscado in k}
            if encontrados:
                for k, v in encontrados.items():
                    color = "green" if v['stock'] > 0 else "red"
                    st.markdown(f"""<div style="border: 2px solid {color}; padding: 15px; border-radius: 10px; margin-bottom: 10px;">
                        <h3 style="margin:0;">📦 {k.split('_')[-1]}</h3>
                        <p style="margin:0;"><b>Bodega:</b> {v['deposito']} | <b>Marca:</b> {v['marca']}</p>
                        <h2 style="margin:0; color:{color};">Stock: {txt_cajas(v['stock'])}</h2>
                    </div>""", unsafe_allow_html=True)
            else: st.error("❌ No encontrado.")

    st.divider()
    if st.button("📦 ABRIR BODEGA", use_container_width=True):
        st.session_state.ver_bodega_abierta = not st.session_state.get('ver_bodega_abierta', False)
        st.rerun()

    if st.session_state.get('ver_bodega_abierta', False):
        d_v = st.selectbox("Selecciona la Bodega:", config["depositos"])
        items_bodega = {k: v for k, v in inv.items() if v['deposito'] == d_v and v['stock'] > 0}
        if items_bodega:
            for kid, info in sorted(items_bodega.items(), key=lambda x: x[1]['marca']):
                st.write(f"🔹 **{kid.split('_')[-1]}** | Marca: {info['marca']} | **Stock: {txt_cajas(info['stock'])}**")
        else: st.warning("No hay stock en esta bodega.")

else:
    # --- MODO PANEL DE TRABAJO (EDICIÓN) ---
    st.header("🛠️ Panel de Trabajo")
    
    # Buscador rápido dentro del panel
    bus_ed = st.text_input("🎯 Buscador rápido para editar:", key="bus_edit").upper().strip()
    if bus_ed:
        for k, v in {k: v for k, v in inv.items() if bus_ed in k}.items():
            mostrar_tarjeta(k, v, "rap")
    
    st.divider()
    
    # Navegación por Marcas y Bodegas (Esto es lo que había desaparecido)
    st.subheader("📋 Inventario por Categorías")
    dep_p = st.selectbox("Filtrar por Bodega:", config["depositos"], key="sel_dep_edit")
    mlist_e = config["marcas"] if config["marcas"] else ["GENERAL"]
    tabs_e = st.tabs(mlist_e)
    
    for i, m_p in enumerate(mlist_e):
        with tabs_e[i]:
            it_p = {k: v for k, v in inv.items() if v['marca']==m_p and v['deposito']==dep_p}
            if it_p:
                for k, v in sorted(it_p.items()):
                    mostrar_tarjeta(k, v, f"pan_{i}")
            else:
                st.write(f"No hay artículos de **{m_p}** en **{dep_p}**.")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔐 Acceso")
    if not st.session_state.get('edit_mode'):
        u = st.selectbox("Usuario", list(config["usuarios"].keys()))
        p = st.text_input("Clave", type="password")
        if st.button("🔓 Entrar"):
            if config["usuarios"].get(u) == p:
                st.session_state.edit_mode, st.session_state.usuario_actual = True, u
                st.toast(f"Bienvenido {u}", icon="👋")
                st.rerun()
    else:
        st.write(f"👤 **{st.session_state.usuario_actual}**")
        if st.button("⚙️ PANEL" if not st.session_state.get('modo_panel') else "🏠 INICIO", use_container_width=True):
            st.session_state.modo_panel = not st.session_state.get('modo_panel', False)
            st.rerun()

        with st.expander("🆕 Nuevo Artículo"):
            nma = st.selectbox("Marca", config["marcas"], key="nw_m")
            nco = st.text_input("Código", key="nw_c").upper().strip()
            nbo = st.selectbox("Bodega", config["depositos"], key="nw_b")
            if st.button("💾 Crear Artículo"):
                if nco and guardar_cambio_google(sh, "INVENTARIO", "NUEVO_ITEM", [nma, nbo, nco, 0]):
                    recargar(); st.rerun()

        if st.session_state.usuario_actual.upper() == "ADMIN":
            with st.expander("👤 Usuarios"):
                un = st.text_input("Nombre").upper().strip()
                uc = st.text_input("Clave", type="password")
                if st.button("🚀 Crear"):
                    guardar_cambio_google(sh, "CONFIG", "MANAGE_USER", [un, uc, "CREAR"])
                    recargar(); st.rerun()
            with st.expander("🏷️ Marcas"):
                nm = st.text_input("Añadir Marca").upper().strip()
                if st.button("➕ Añadir"):
                    guardar_cambio_google(sh, "CONFIG", "ADD_CONFIG", [nm, 4])
                    recargar(); st.rerun()
            with st.expander("🏘️ Bodegas"):
                nb_a = st.text_input("Añadir Bodega").upper().strip()
                if st.button("➕ Añadir Bodega"):
                    guardar_cambio_google(sh, "CONFIG", "ADD_CONFIG", [nb_a, 3])
                    recargar(); st.rerun()

            if st.button("📜 VER HISTORIAL", use_container_width=True):
                st.session_state.ver_historial = True
                st.rerun()

        if st.button("🔒 Salir", use_container_width=True):
            st.session_state.edit_mode = False
            st.rerun()
