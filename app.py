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
        st.error(f"Error de conexión: {e}")
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
            # Buscamos el código en la columna 3 (CODIGO)
            codigo_puro = str(datos[0].split("_")[-1])
            celda = ws.find(codigo_puro, in_column=3)
            if celda:
                ws.update_cell(celda.row, 4, int(datos[1])) # Actualiza columna 4 (STOCK)
                return True
        elif accion == "ADD_LOG":
            hora = (datetime.now() - timedelta(hours=4)).strftime("%d/%m/%Y %H:%M")
            ws.append_row([hora] + datos)
            return True
        elif accion == "NUEVO_ITEM":
            ws.append_row(datos)
            return True
    except Exception as e:
        st.error(f"⚠️ Error al guardar: {e}")
        return False

def txt_cajas(n):
    return f"{n} caja" if n == 1 else f"{n} cajas"

# --- 2. INICIALIZACIÓN ---
st.set_page_config(page_title="Bodega Pro Ultra", layout="wide")

def recargar():
    # Limpiamos caché interno para forzar lectura
    st.session_state.inv, st.session_state.config, st.session_state.logs, st.session_state.sh = cargar_datos_google()

if 'data_loaded' not in st.session_state:
    recargar()
    st.session_state.data_loaded = True

inv, config, logs, sh = st.session_state.inv, st.session_state.config, st.session_state.logs, st.session_state.sh

if 'edit_mode' not in st.session_state: st.session_state.edit_mode = False
if 'modo_panel' not in st.session_state: st.session_state.modo_panel = False
if 'ver_historial' not in st.session_state: st.session_state.ver_historial = False

# --- DIALOGOS ---
@st.dialog("Confirmar Movimiento")
def confirmar_mov(k, v, cant, op):
    st.warning(f"¿Confirmas {op} {txt_cajas(cant)} a {k.split('_')[-1]}?")
    c1, c2 = st.columns(2)
    if c1.button("SÍ, GUARDAR", use_container_width=True):
        nuevo_stock = v['stock'] + cant if op == 'SUMAR' else v['stock'] - cant
        exito = guardar_cambio_google(sh, "INVENTARIO", "UPDATE_STOCK", [k, nuevo_stock])
        if exito:
            guardar_cambio_google(sh, "LOGS", "ADD_LOG", [st.session_state.usuario_actual, op, f"{txt_cajas(cant)} de {k}"])
            st.success("¡Guardado correctamente!")
            recargar()
            st.rerun()
        else:
            st.error("No se pudo actualizar en Google Sheets.")
    if c2.button("CANCELAR", use_container_width=True): st.rerun()

# --- INTERFAZ ---
st.title("🏢 Bodega Central")

if not st.session_state.modo_panel:
    # --- BUSCADOR ---
    st.subheader("🔍 Buscar Producto")
    c_input, c_ok = st.columns([4, 1])
    codigo_buscado = c_input.text_input("Ingresa el código:", placeholder="Escribe aquí...", label_visibility="collapsed").upper().strip()
    
    if c_ok.button("🔍 OK", use_container_width=True) or (codigo_buscado and st.session_state.get('last_code') != codigo_buscado):
        if codigo_buscado:
            encontrados = {k: v for k, v in inv.items() if codigo_buscado in k}
            if encontrados:
                for k, v in encontrados.items():
                    color = "green" if v['stock'] > 0 else "red"
                    st.markdown(f"""
                    <div style="border: 2px solid {color}; padding: 15px; border-radius: 10px; margin-bottom: 10px;">
                        <h3 style="margin:0;">📦 {k.split('_')[-1]}</h3>
                        <p style="margin:0;"><b>Bodega:</b> {v['deposito']} | <b>Marca:</b> {v['marca']}</p>
                        <h2 style="margin:0; color:{color};">Stock: {txt_cajas(v['stock'])}</h2>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.error("❌ No se encontró ese código.")

    st.divider()

    if st.button("📦 ABRIR BODEGA", use_container_width=True):
        st.session_state.ver_menu_marcas = not st.session_state.get('ver_menu_marcas', False)
        st.rerun()

    if st.session_state.get('ver_menu_marcas', False):
        d_v = st.selectbox("Selecciona la Bodega:", config["depositos"])
        items_bodega = {k: v for k, v in inv.items() if v['deposito'] == d_v and v['stock'] > 0}
        if items_bodega:
            for kid, info in sorted(items_bodega.items(), key=lambda x: x[1]['marca']):
                st.write(f"🔹 **{kid.split('_')[-1]}** | Marca: {info['marca']} | **Stock: {txt_cajas(info['stock'])}**")
        else:
            st.warning("No hay artículos con stock en esta bodega.")

# --- SIDEBAR (Mantenemos igual para no romper nada) ---
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
        if st.button("⚙️ PANEL" if not st.session_state.modo_panel else "🏠 INICIO", use_container_width=True):
            st.session_state.modo_panel = not st.session_state.modo_panel
            st.rerun()
        
        # ... El resto del sidebar de gestión de marcas/bodegas se mantiene igual ...
