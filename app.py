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
            # Esto convierte los \n del texto en saltos de línea reales
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name('creds.json', SCOPE)
            
        return gspread.authorize(creds).open(NOMBRE_EXCEL)
    except Exception as e:
        st.error(f"❌ Error de conexión: {e}")
        return None
        
# --- FUNCIONES DE BASE DE DATOS (NUEVAS PARA GOOGLE) ---
def cargar_datos_google():
    sh = conectar_google()
    if not sh: return {}, {}, [], None
    
    # 1. Cargar Inventario
    ws_inv = sh.worksheet("INVENTARIO")
    datos_inv = ws_inv.get_all_records()
    inv = {f"{r['DEPOSITO']}_{r['CODIGO']}": {"marca": r['MARCA'], "deposito": r['DEPOSITO'], "stock": int(r['STOCK'])} for r in datos_inv}
    
    # 2. Cargar Configuración
    ws_conf = sh.worksheet("CONFIG")
    df_conf = pd.DataFrame(ws_conf.get_all_records())
    config = {
        "usuarios": {str(r['USUARIO']): str(r['CLAVE']) for _, r in df_conf.iterrows() if r['USUARIO']},
        "depositos": list(df_conf['DEPOSITOS'].dropna().unique()),
        "marcas": list(df_conf['MARCAS'].dropna().unique())
    }
    
    # 3. Cargar Logs (últimos 50)
    ws_log = sh.worksheet("LOGS")
    logs = ws_log.get_all_records()[-50:]
    logs.reverse() # Los más nuevos primero
    
    return inv, config, logs, sh

def guardar_movimiento_google(sh, id_f, nuevo_stock, usuario, accion, detalle):
    try:
        # Actualizar Inventario
        ws_inv = sh.worksheet("INVENTARIO")
        depo, cod = id_f.split("_", 1)
        # Buscar la fila del código
        celda = ws_inv.find(cod)
        ws_inv.update_cell(celda.row, 4, nuevo_stock) # Columna 4 = STOCK
        
        # Registrar Log
        ws_log = sh.worksheet("LOGS")
        hora = (datetime.now() - timedelta(hours=4)).strftime("%d/%m/%Y %H:%M")
        ws_log.append_row([hora, usuario, accion, detalle])
    except:
        st.error("Error al actualizar Google Sheets")

# --- INICIO DE LA APP ---
st.set_page_config(page_title="Bodega Pro Ultra", layout="wide")

# Carga inicial desde Google
inv, config, logs, sh = cargar_datos_google()

# ... (Aquí sigue todo tu código de interfaz: mostrar_item_edicion, sidebar, etc.)
# IMPORTANTE: Cambia las llamadas a guardar_todo() por guardar_movimiento_google()
