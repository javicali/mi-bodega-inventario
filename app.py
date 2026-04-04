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

def cargar_datos_google():
    try:
        sh = conectar_google()
        if not sh: 
            st.error("No se pudo conectar con el archivo de Google Sheets.")
            return {}, {}, [], None
        
        # 1. Cargar Inventario (Pestaña INVENTARIO)
        ws_inv = sh.worksheet("INVENTARIO")
        datos_inv = ws_inv.get_all_records()
        inv = {f"{r['DEPOSITO']}_{r['CODIGO']}": {"marca": r['MARCA'], "deposito": r['DEPOSITO'], "stock": int(r['STOCK'])} for r in datos_inv if r.get('CODIGO')}
        
        # 2. Cargar Configuración (Pestaña CONFIG)
        ws_conf = sh.worksheet("CONFIG")
        datos_conf = ws_conf.get_all_records()
        
        # Si la configuración está vacía, ponemos valores por defecto para que no salga pantalla blanca
        if not datos_conf:
            config = {"usuarios": {"ADMIN": "123"}, "depositos": ["BODEGA 1"], "marcas": ["GENERAL"]}
        else:
            df_conf = pd.DataFrame(datos_conf)
            config = {
                "usuarios": {str(r['USUARIO']): str(r['CLAVE']) for _, r in df_conf.iterrows() if r.get('USUARIO')},
                "depositos": [x for x in df_conf['DEPOSITOS'].unique() if x] if 'DEPOSITOS' in df_conf else ["BODEGA 1"],
                "marcas": [x for x in df_conf['MARCAS'].unique() if x] if 'MARCAS' in df_conf else ["GENERAL"]
            }
        
        # 3. Cargar Logs (Pestaña LOGS)
        ws_log = sh.worksheet("LOGS")
        logs = ws_log.get_all_records()[-50:]
        logs.reverse()
        
        return inv, config, logs, sh
    except Exception as e:
        st.error(f"Error procesando los datos del Excel: {e}")
        # Retornamos valores vacíos para evitar la pantalla blanca
        return {}, {"usuarios": {"ADMIN": "123"}, "depositos": [], "marcas": []}, [], None      
        
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
