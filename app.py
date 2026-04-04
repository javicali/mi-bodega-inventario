import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import re
from datetime import datetime, timedelta
import io

# --- 1. CONFIGURACIÓN ---
NOMBRE_EXCEL = "DB_BODEGA_SISTEMA"
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# --- 2. LA PIEZA QUE FALTABA: FUNCIÓN DE CONEXIÓN ---
def conectar_google():
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            # Reparamos la llave para que Python la entienda
            if "private_key" in creds_dict:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
        else:
            # Por si pruebas en local
            creds = ServiceAccountCredentials.from_json_keyfile_name('creds.json', SCOPE)
            
        client = gspread.authorize(creds)
        return client.open(NOMBRE_EXCEL)
    except Exception as e:
        st.error(f"❌ Error crítico de conexión: {e}")
        return None

# --- 3. FUNCIÓN PARA CARGAR LOS DATOS ---
def cargar_datos_google():
    try:
        sh = conectar_google()
        if not sh: return {}, {}, [], None
        
        # Cargar Inventario
        ws_inv = sh.worksheet("INVENTARIO")
        datos_inv = ws_inv.get_all_records()
        inv = {f"{r['DEPOSITO']}_{r['CODIGO']}": {"marca": r['MARCA'], "deposito": r['DEPOSITO'], "stock": int(r['STOCK'])} for r in datos_inv if r.get('CODIGO')}
        
        # Cargar Configuración
        ws_conf = sh.worksheet("CONFIG")
        df_conf = pd.DataFrame(ws_conf.get_all_records())
        
        if df_conf.empty:
            config = {"usuarios": {"ADMIN": "123"}, "depositos": ["BODEGA 1"], "marcas": ["GENERAL"]}
        else:
            config = {
                "usuarios": {str(r['USUARIO']): str(r['CLAVE']) for _, r in df_conf.iterrows() if 'USUARIO' in r and r['USUARIO']},
                "depositos": [x for x in df_conf['DEPOSITOS'].unique() if x] if 'DEPOSITOS' in df_conf else ["BODEGA 1"],
                "marcas": [x for x in df_conf['MARCAS'].unique() if x] if 'MARCAS' in df_conf else ["GENERAL"]
            }
        
        # Cargar Logs
        ws_log = sh.worksheet("LOGS")
        logs = ws_log.get_all_records()[-50:]
        logs.reverse()
        
        return inv, config, logs, sh
    except Exception as e:
        st.error(f"Error al leer las hojas del Excel: {e}")
        return {}, {"usuarios": {"ADMIN": "123"}, "depositos": [], "marcas": []}, [], None

# --- 4. FUNCIÓN PARA GUARDAR ---
def guardar_movimiento_google(sh, id_f, nuevo_stock, usuario, accion, detalle):
    try:
        if not sh: return
        ws_inv = sh.worksheet("INVENTARIO")
        depo, cod = id_f.split("_", 1)
        celda = ws_inv.find(cod)
        if celda:
            ws_inv.update_cell(celda.row, 4, nuevo_stock) # Columna 4 es STOCK
        
        ws_log = sh.worksheet("LOGS")
        hora = (datetime.now() - timedelta(hours=4)).strftime("%d/%m/%Y %H:%M")
        ws_log.append_row([hora, usuario, accion, detalle])
    except Exception as e:
        st.error(f"No se pudo guardar en Google: {e}")

# --- 5. INICIO DE LA INTERFAZ ---
st.set_page_config(page_title="Bodega Pro Ultra", layout="wide")

# Carga inicial
inv, config, logs, sh = cargar_datos_google()
