import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import json
from datetime import datetime, timedelta

# --- CONFIGURACIÓN GOOGLE SHEETS ---
NOMBRE_EXCEL = "DB_BODEGA_SISTEMA"
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def conectar_google():
    try:
        # 1. Si estamos en la NUBE (Streamlit Secrets)
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            
            # REPARACIÓN DE LLAVE: Limpia espacios y saltos de línea
            raw_key = creds_dict["private_key"].strip().replace("\\n", "\n")
            creds_dict["private_key"] = raw_key
            
            # USAMOS EL MÉTODO CORRECTO PARA DICCIONARIOS
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
        
        # 2. Si estamos en la iMac (Local)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name('creds.json', SCOPE)
            
        client = gspread.authorize(creds)
        return client.open(NOMBRE_EXCEL)
        
    except Exception as e:
        st.error(f"❌ Error de conexión: {e}")
        return None
        
# --- FUNCIONES DE BASE DE DATOS ---
def cargar_todo():
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
        "usuarios": {r['USUARIO']: str(r['CLAVE']) for _, r in df_conf.iterrows() if r['USUARIO']},
        "depositos": list(df_conf['DEPOSITOS'].dropna().unique()),
        "marcas": list(df_conf['MARCAS'].dropna().unique())
    }
    
    # 3. Cargar Logs (últimos 50)
    ws_log = sh.worksheet("LOGS")
    logs = ws_log.get_all_records()[-50:]
    
    return inv, config, logs, sh

def guardar_movimiento(sh, id_f, nuevo_stock, usuario, accion, detalle):
    # Actualizar Celda en Inventario
    ws_inv = sh.worksheet("INVENTARIO")
    depo, cod = id_f.split("_", 1)
    try:
        celda = ws_inv.find(cod)
        ws_inv.update_cell(celda.row, 4, nuevo_stock) # Columna 4 es STOCK
        
        # Registrar en LOGS del Excel
        ws_log = sh.worksheet("LOGS")
        hora = (datetime.now() - timedelta(hours=4)).strftime("%d/%m/%Y %H:%M")
        ws_log.append_row([hora, usuario, accion, detalle])
    except:
        st.error("No se encontró el código en el Excel para actualizar.")

# --- INTERFAZ (Tu diseño original adaptado) ---
st.set_page_config(page_title="Bodega Cloud Pro", layout="wide")
inv, config, logs, sh = cargar_todo()

if 'edit_mode' not in st.session_state: st.session_state.edit_mode = False

# --- LÓGICA DE BOTONES (Ejemplo para Sumar) ---
# Cuando presiones el botón de CONFIRMAR en tu app:
# nuevo_val = inv[id_f]["stock"] + cant
# guardar_movimiento(sh, id_f, nuevo_val, usuario, "SUMA", f"+{cant} {id_f}")
