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
            todo = ws.get_all_values(); [ws.delete_rows(i) for i, f in enumerate(todo[1:], 2) if str(f[2]).strip().upper() == cod_del]
    except Exception as e: st.error(f"⚠️ Error: {e}")

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
    st.warning(f"¿Confirmas que {op} {txt_cajas(cant)} de {k.split('_')[-1]}?")
    c1, c2 = st.columns(2)
    if c1.button("SÍ, GUARDAR", use_container_width=True):
        nuevo = v['stock'] + cant if op == 'ENTRÓ' else v['stock'] - cant
        guardar_cambio_google(sh, "INVENTARIO", "UPDATE_STOCK", [k, nuevo])
        det = f"{txt_cajas(cant)} de {k.split('_')[-1]} {'a' if op == 'ENTRÓ' else 'de'} {k.split('_')[0]}"
        guardar_cambio_google(sh, "LOGS", "ADD_LOG", [st.session_state.usuario_actual, op, det])
        # REINICIAR EL CONTADOR A 0 AL TERMINAR
        if f"n_val_{k}" in st.session_state: st.session_state[f"n_val_{k}"] = 0
        st.toast(f"✅ Registrado!"); recargar(); st.rerun()
    if c2.button("CANCELAR", use_container_width=True): st.rerun()

def mostrar_tarjeta(k, v, suf):
    # Creamos un estado para el número si no existe, iniciando en 0
    key_input = f"n_val_{k}"
    if key_input not in st.session_state: st.session_state[key_input] = 0

    with st.container(border=True):
        c1, c2, c3 = st.columns([2, 1, 3.5]) 
        c1.markdown(f"**{k.split('_')[-1]}**\n<small>{v['marca']} | {v['deposito']}</small>", unsafe_allow_html=True)
        c2.write(f"📦 {v['stock']}")
        with c3:
            # Ahora el valor está vinculado al session_state
            cant = st.number_input("n", min_value=0, key=key_input, label_visibility="collapsed")
            cols_btn = st.columns([1, 1, 0.5]) 
            if cols_btn[0].button("ENTRÓ", key=f"btn_a_{suf}_{k}", use_container_width=True):
                if cant > 0: confirmar_mov(k, v, cant, "ENTRÓ")
                else: st.error("Escribe una cantidad")
            if cols_btn[1].button("SALIÓ", key=f"btn_s_{suf}_{k}", disabled=v['stock']<cant or cant==0, use_container_width=True):
                confirmar_mov(k, v, cant, "SALIÓ")

# --- 3. INTERFAZ ---
st.title("🏢 Bodega Central")

if st.session_state.get('ver_historial', False):
    if st.button("⬅️ Volver"): st.session_state.ver_historial = False; st.rerun()
    st.dataframe(pd.DataFrame(logs).iloc[::-1], use_container_width=True)
elif not st.session_state.get('modo_panel', False):
    st.subheader("🔍 Consulta")
    c_in, c_ok, c_cl = st.columns([4, 1, 1])
    with c_in: bus_p = st.text_input("Cod:", key=f"ip_{st.session_state.reset_pub}", label_visibility="collapsed").upper().strip()
    with c_ok: btn_ok = st.button("🔍 OK", use_container_width=True)
    with c_cl: 
        if bus_p and st.button("🧹", key="cp"): st.session_state.reset_pub += 1; st.rerun()
    if bus_p or btn_ok:
        for k, v in {k: v for k, v in inv.items() if k.split('_')[-1] == bus_p}.items():
            col = "green" if v['stock'] > 0 else "red"
            st.markdown(f'<div style="border:2px solid {col};padding:10px;border-radius:10px;"><h3>📦 {k.split("_")[-1]}</h3><h2 style="color:{col};">{txt_cajas(v["stock"])}</h2></div>', unsafe_allow_html=True)
    st.divider()
    if st.button("📦 VER LISTADO POR BODEGA", use_container_width=True):
        st.session_state.v_m = not st.session_state.get('v_m', False); st.rerun()
    if st.session_state.get('v_m', False):
        d_v = st.selectbox("Bodega:", config["depositos"])
        orden = st.selectbox("Orden:", ["A-Z", "Mayor Stock", "Menor Stock"])
        final = [{'c': k.split('_')[-1], 'm': v['marca'], 's': v['stock']} for k, v in inv.items() if v['deposito'].upper() == d_v.upper() and v['stock'] > 0]
        if orden == "A-Z": final.sort(key=lambda x: x['c'])
        elif orden == "Mayor Stock": final.sort(key=lambda x: x['s'], reverse=True)
        for item in final: st.write(f"📦 **{item['c']}** | {item['m']} | **{txt_cajas(item['s'])}**")
else:
    c1, c2 = st.columns([1, 10])
    with c1: 
        if st.button("🏠"): st.session_state.modo_panel = False; st.rerun()
    st.header("Entrada / Salida 📦")
    ci, co, cl = st.columns([4, 1, 1])
    with ci: bus_e = st.text_input("🎯 Cod:", key=f"ie_{st.session_state.reset_pan}", label_visibility="collapsed").upper().strip()
    with co: btn_e = st.button("🔍", key="be", use_container_width=True)
    with cl: 
        if bus_e and st.button("🧹", key="ce"): st.session_state.reset_pan += 1; st.rerun()
    if bus_e or btn_e:
        enc = {k: v for k, v in inv.items() if k.split('_')[-1] == bus_e}
        if enc: 
            for k, v in enc.items(): mostrar_tarjeta(k, v, "r")
        else: st.info("No encontrado")
    st.divider()
    dep_p = st.selectbox("Bodega:", config["depositos"])
    tabs = st.tabs(config["marcas"])
    for i, m in enumerate(config["marcas"]):
        with tabs[i]:
            for k, v in sorted({k: v for k, v in inv.items() if v['marca'].upper()==m.upper() and v['deposito'].upper()==dep_p.upper()}.items()):
                mostrar_tarjeta(k, v, f"p_{i}")

# --- SIDEBAR ---
with st.sidebar:
    if not st.session_state.get('edit_mode', False):
        u, p = st.selectbox("Usuario", list(config["usuarios"].keys())), st.text_input("Clave", type="password")
        if st.button("🔓 Entrar"):
            if config["usuarios"].get(u) == p: st.session_state.edit_mode, st.session_state.usuario_actual = True, u; st.rerun()
    else:
        st.write(f"👤 **{st.session_state.usuario_actual}**")
        if st.button("📦 ENTRADA/SALIDA" if not st.session_state.get('modo_panel', False) else "🏠 INICIO", use_container_width=True):
            st.session_state.modo_panel = not st.session_state.get('modo_panel', False); st.rerun()
        with st.expander("🆕 Nuevo Código"):
            nma, nco, nbo = st.selectbox("Marca", config["marcas"]), st.text_input("Código").upper().strip(), st.selectbox("Bodega", config["depositos"])
            if st.button("💾 Crear") and nco: guardar_cambio_google(sh, "INVENTARIO", "NUEVO_ITEM", [nma, nbo, nco, 0]); recargar(); st.rerun()
        if st.session_state.usuario_actual.upper() == "ADMIN":
            if st.button("📜 HISTORIAL", use_container_width=True): st.session_state.ver_historial = True; st.rerun()
            st.download_button("📊 REPORTE EXCEL", generar_excel_reporte(inv), "Reporte.xlsx", use_container_width=True)
        if st.button("🔒 Salir", use_container_width=True): st.session_state.edit_mode = False; st.rerun()
