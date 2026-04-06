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
        inv = {f"{str(r['DEPOSITO']).strip().upper()}_{str(r['CODIGO']).strip().upper()}": {"marca": r['MARCA'], "deposito": r['DEPOSITO'], "stock": int(r['STOCK'])} 
               for r in datos_inv if str(r.get('CODIGO')).strip()}
        ws_conf = sh.worksheet("CONFIG")
        df_conf = pd.DataFrame(ws_conf.get_all_records())
        list_users = {str(r['USUARIO']).strip(): str(r['CLAVE']).strip() for _, r in df_conf.iterrows() if str(r.get('USUARIO')).strip()}
        list_depos = [str(x).strip().upper() for x in df_conf['DEPOSITOS'].unique() if str(x).strip()] if 'DEPOSITOS' in df_conf else []
        list_marcas = [str(x).strip().upper() for x in df_conf['MARCAS'].unique() if str(x).strip()] if 'MARCAS' in df_conf else []
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
            id_comb = datos[0]
            cod_buscado = str(id_comb.split("_")[-1]).strip().upper()
            bod_buscada = str(id_comb.split("_")[0]).strip().upper()
            nuevo_stock = int(datos[1])
            todo = ws.get_all_values()
            headers = [h.strip().upper() for h in todo[0]]
            idx_dep, idx_cod, idx_stk = headers.index("DEPOSITO"), headers.index("CODIGO"), headers.index("STOCK")
            fila_real = None
            for i, fila in enumerate(todo[1:], start=2):
                if str(fila[idx_dep]).strip().upper() == bod_buscada and str(fila[idx_cod]).strip().upper() == cod_buscado:
                    fila_real = i
                    break
            if fila_real: ws.update_cell(fila_real, idx_stk + 1, nuevo_stock)
        elif accion == "ADD_LOG":
            hora = (datetime.now() - timedelta(hours=4)).strftime("%d/%m/%Y %H:%M")
            ws.append_row([hora] + datos)
        elif accion == "NUEVO_ITEM": ws.append_row(datos)
        elif accion == "BORRAR_ITEM":
            cod_del = str(datos[0].split("_")[-1]).strip().upper()
            todo = ws.get_all_values()
            for i, f in enumerate(todo[1:], 2):
                if str(f[2]).strip().upper() == cod_del: ws.delete_rows(i); break
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
    except Exception as e: st.error(f"⚠️ Error: {e}")

def txt_cajas(n): return f"{n} caja" if n == 1 else f"{n} cajas"

# --- 2. INICIALIZACIÓN ---
st.set_page_config(page_title="Bodega Central", layout="wide")

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
    st.warning(f"¿Confirmas que {op} {txt_cajas(cant)} de {k.split('_')[-1]}?")
    c1, c2 = st.columns(2)
