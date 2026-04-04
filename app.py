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

import re

def conectar_google():
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            
            # --- LIMPIEZA Y REPARACIÓN MAESTRA ---
            raw_key = creds_dict["private_key"]
            
            # 1. Extraemos solo el corazón de la llave
            if "-----BEGIN PRIVATE KEY-----" in raw_key:
                key_body = raw_key.split("-----BEGIN PRIVATE KEY-----")[1].split("-----END PRIVATE KEY-----")[0]
                
                # 2. Quitamos espacios, saltos de línea y basura invisible
                clean_key = re.sub(r'\s+', '', key_body)
                
                # 3. AUTO-REPARACIÓN DE PADDING (El truco final)
                # Si a la llave le faltan caracteres para ser múltiplo de 4, se los ponemos
                missing_padding = len(clean_key) % 4
                if missing_padding:
                    clean_key += '=' * (4 - missing_padding)
                
                # 4. Reconstruimos la llave perfecta
                creds_dict["private_key"] = f"-----BEGIN PRIVATE KEY-----\n{clean_key}\n-----END PRIVATE KEY-----\n"
            
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
        else:
            # Respaldo para tu iMac
            creds = ServiceAccountCredentials.from_json_keyfile_name('creds.json', SCOPE)
            
        client = gspread.authorize(creds)
        return client.open(NOMBRE_EXCEL)
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
