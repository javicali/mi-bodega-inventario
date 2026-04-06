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
            id_combinado = datos[0] 
            codigo_solo = str(id_combinado.split("_")[-1]).strip()
            bodega_sola = str(id_combinado.split("_")[0]).strip()
            nuevo_stock = datos[1]

            # LEER TODA LA HOJA PARA BUSCAR POR ENCABEZADOS
            data = ws.get_all_records()
            fila_idx = None
            for i, row in enumerate(data):
                # Buscamos la fila que coincida en DEPOSITO y CODIGO
                if str(row.get('DEPOSITO')).strip() == bodega_sola and str(row.get('CODIGO')).strip() == codigo_solo:
                    fila_idx = i + 2 # +2 porque get_all_records no cuenta cabecera y Google empieza en 1
                    break
            
            if fila_idx:
                # Buscamos en qué columna está el "STOCK" dinámicamente
                headers = ws.row_values(1)
                col_stock = headers.index("STOCK") + 1
                ws.update_cell(fila_idx, col_stock, nuevo_stock)
            else:
                st.error(f"❌ No encontré {codigo_solo} en {bodega_sola}. Verifica que los nombres en el Excel coincidan exactamente.")

        elif accion == "ADD_LOG":
            hora = (datetime.now() - timedelta(hours=4)).strftime("%d/%m/%Y %H:%M")
            ws.append_row([hora] + datos)
        elif accion == "NUEVO_ITEM": ws.append_row(datos)
        elif accion == "BORRAR_ITEM":
            codigo_a_borrar = str(datos[0].split("_")[-1]).strip()
            celda = ws.find(codigo_a_borrar)
            if celda: ws.delete_rows(celda.row)
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
    except Exception as e:
        st.error(f"⚠️ Error: {e}")

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
    partes = k.split("_")
    nombre_bodega = partes[0]
    codigo_prod = partes[-1]
    st.warning(f"¿Confirmas que {op} {txt_cajas(cant)} de {codigo_prod}?")
    c1, c2 = st.columns(2)
    if c1.button("SÍ, GUARDAR", use_container_width=True):
        nuevo = v['stock'] + cant if op == 'ENTRÓ' else v['stock'] - cant
        guardar_cambio_google(sh, "INVENTARIO", "UPDATE_STOCK", [k, nuevo])
        preposicion = "a" if op == "ENTRÓ" else "de"
        detalle_log = f"{txt_cajas(cant)} de {codigo_prod} {preposicion} {nombre_bodega}"
        guardar_cambio_google(sh, "LOGS", "ADD_LOG", [st.session_state.usuario_actual, op, detalle_log])
        st.toast(f"✅ ¡{op} registrado!", icon='📦')
        recargar(); st.rerun()
    if c2.button("CANCELAR", use_container_width=True): st.rerun()

@st.dialog("Eliminar Código")
def confirmar_eliminar(k):
    st.error(f"¿Estás seguro de eliminar {k.split('_')[-1]} permanentemente?")
    c1, c2 = st.columns(2)
    if c1.button("ELIMINAR", use_container_width=True):
        guardar_cambio_google(sh, "INVENTARIO", "BORRAR_ITEM", [k])
        guardar_cambio_google(sh, "LOGS", "ADD_LOG", [st.session_state.usuario_actual, "ELIMINÓ", f"Código {k.split('_')[-1]} de {k.split('_')[0]}"])
        st.toast(f"🗑️ Código eliminado", icon='🗑️')
        recargar(); st.rerun()
    if c2.button("CANCELAR", use_container_width=True): st.rerun()

def mostrar_tarjeta(k, v, suf):
    with st.container(border=True):
        c1, c2, c3 = st.columns([2, 1, 3.5]) 
        c1.markdown(f"**{k.split('_')[-1]}**\n<small>{v['marca']} | {v['deposito']}</small>", unsafe_allow_html=True)
        c2.write(f"📦 {v['stock']}")
        with c3:
            cant = st.number_input("n", min_value=1, key=f"n_{suf}_{k}", label_visibility="collapsed")
            cols_btn = st.columns([1, 1, 0.5]) 
            if cols_btn[0].button("ENTRÓ", key=f"btn_add_{suf}_{k}", use_container_width=True): confirmar_mov(k, v, cant, "ENTRÓ")
            if cols_btn[1].button("SALIÓ", key=f"btn_sub_{suf}_{k}", disabled=v['stock']<cant, use_container_width=True): confirmar_mov(k, v, cant, "SALIÓ")
            if v['stock'] == 0:
                if cols_btn[2].button("🗑️", key=f"del_{suf}_{k}"): confirmar_eliminar(k)

# --- 3. INTERFAZ ---
st.title("🏢 Bodega Central")

if st.session_state.get('ver_historial', False):
    st.header("📜 Historial")
    if st.button("⬅️ Volver"): st.session_state.ver_historial = False; st.rerun()
    st.dataframe(pd.DataFrame(logs).iloc[::-1], use_container_width=True)
elif not st.session_state.get('modo_panel', False):
    st.subheader("🔍 Consulta")
    col_input, col_lupa, col_clear = st.columns([4, 1, 1])
    with col_input: 
        bus_p = st.text_input("Código:", key=f"in_pub_{st.session_state.reset_pub}", label_visibility="collapsed").upper().strip()
    with col_lupa: 
        btn_lupa = st.button("🔍 OK", key="btn_lupa_pub", use_container_width=True)
    with col_clear:
        if bus_p:
            if st.button("🧹", key="btn_clear_pub", use_container_width=True):
                st.session_state.reset_pub += 1; st.rerun()
            
    if bus_p or btn_lupa:
        enc = {k: v for k, v in inv.items() if str(k.split('_')[-1]) == bus_p}
        for k, v in enc.items():
            color = "green" if v['stock'] > 0 else "red"
            st.markdown(f'<div style="border:2px solid {color};padding:15px;border-radius:10px;"><h3>📦 {k.split("_")[-1]}</h3><p>{v["deposito"]} | {v["marca"]}</p><h2 style="color:{color};">{txt_cajas(v["stock"])}</h2></div>', unsafe_allow_html=True)
    st.divider()
    if st.button("📦 VER LISTADO POR BODEGA", use_container_width=True):
        st.session_state.ver_menu_marcas = not st.session_state.get('ver_menu_marcas', False); st.rerun()
    if st.session_state.get('ver_menu_marcas', False):
        d_v = st.selectbox("Bodega:", config["depositos"])
        orden = st.selectbox("Ordenar:", ["A-Z", "Mayor Stock", "Menor Stock"])
        final = [{'codigo': k.split('_')[-1], 'marca': v['marca'], 'stock': v['stock']} for k, v in inv.items() if v['deposito'] == d_v and v['stock'] > 0]
        if orden == "A-Z": final.sort(key=lambda x: x['codigo'])
        elif orden == "Mayor Stock": final.sort(key=lambda x: x['stock'], reverse=True)
        for item in final: st.write(f"📦 **{item['codigo']}** | {item['marca']} | **{txt_cajas(item['stock'])}**")
else:
    c1, c2 = st.columns([1, 10])
    with c1:
        if st.button("🏠", help="Volver a Inicio"):
            st.session_state.modo_panel = False; st.rerun()
    with c2:
        st.header("Entrada / Salida 📦")

    col_in_p, col_btn_p, col_clr_p = st.columns([4, 1, 1])
    with col_in_p: 
        bus_e = st.text_input("🎯 Código:", key=f"in_pan_{st.session_state.reset_pan}", label_visibility="collapsed").upper().strip()
    with col_btn_p: 
        btn_lupa_p = st.button("🔍", key="btn_lupa_pan", use_container_width=True)
    with col_clear: # Se añadió la lógica del botón limpiar aquí también
        if bus_e:
            if st.button("🧹", key="btn_clear_pan", use_container_width=True):
                st.session_state.reset_pan += 1; st.rerun()
    
    if bus_e or btn_lupa_p:
        enc_ed = {k: v for k, v in inv.items() if str(k.split('_')[-1]) == bus_e}
        if enc_ed:
            for k, v in enc_ed.items(): mostrar_tarjeta(k, v, "rap")
        elif bus_e:
            st.info("Código no encontrado")
    
    st.divider()
    dep_p = st.selectbox("Bodega:", config["depositos"])
    tabs_e = st.tabs(config["marcas"] if config["marcas"] else ["GENERAL"])
    for i, m_p in enumerate(config["marcas"]):
        with tabs_e[i]:
            for k, v in sorted({k: v for k, v in inv.items() if v['marca']==m_p and v['deposito']==dep_p}.items()):
                mostrar_tarjeta(k, v, f"pan_{i}")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔐 Acceso")
    if not st.session_state.get('edit_mode', False):
        u = st.selectbox("Usuario", list(config["usuarios"].keys()))
        p = st.text_input("Clave", type="password")
        if st.button("🔓 Entrar"):
            if config["usuarios"].get(u) == p:
                st.session_state.edit_mode, st.session_state.usuario_actual = True, u
                st.toast(f"Bienvenido {u}"); st.rerun()
            else: st.error("Error")
    else:
        st.write(f"👤 **{st.session_state.usuario_actual}**")
        if st.button("📦 ENTRADA/SALIDA" if not st.session_state.get('modo_panel', False) else "🏠 INICIO", use_container_width=True):
            st.session_state.modo_panel = not st.session_state.get('modo_panel', False); st.rerun()
        
        with st.expander("🆕 Nuevo Código"):
            nma, nco, nbo = st.selectbox("Marca", config["marcas"]), st.text_input("Código").upper().strip(), st.selectbox("Bodega", config["depositos"])
            if st.button("💾 Crear"):
                if nco: 
                    guardar_cambio_google(sh, "INVENTARIO", "NUEVO_ITEM", [nma, nbo, nco, 0])
                    st.toast("Código creado"); recargar(); st.rerun()

        if st.session_state.usuario_actual.upper() == "ADMIN":
            with st.expander("👤 Gestión de Usuarios"):
                un_c, uc_c = st.text_input("Nuevo Usuario"), st.text_input("Clave nueva", type="password")
                if st.button("🚀 Crear Usuario"):
                    guardar_cambio_google(sh, "CONFIG", "MANAGE_USER", [un_c, uc_c, "CREAR"])
                    st.toast("Usuario creado"); recargar(); st.rerun()
                st.divider()
                u_sel = st.selectbox("Seleccionar Usuario:", [u for u in config["usuarios"].keys() if u != "ADMIN"])
                nueva_pass = st.text_input("Cambiar Contraseña", type="password")
                c1, c2 = st.columns(2)
                if c1.button("💾 Modificar"):
                    guardar_cambio_google(sh, "CONFIG", "MANAGE_USER", [u_sel, nueva_pass, "MODIFICAR"])
                    st.toast("Contraseña actualizada"); recargar(); st.rerun()
                if c2.button("🗑️ Eliminar"):
                    guardar_cambio_google(sh, "CONFIG", "MANAGE_USER", [u_sel, "", "ELIMINAR"])
                    st.toast("Usuario eliminado"); recargar(); st.rerun()

            with st.expander("🏷️ Gestión de Marcas"):
                m_sel = st.selectbox("Seleccionar Marca:", config["marcas"])
                if st.button("🗑️ Eliminar Marca"):
                    guardar_cambio_google(sh, "CONFIG", "DEL_CONFIG", [m_sel, 4])
                    st.toast("Marca eliminada"); recargar(); st.rerun()
                st.divider()
                nm_nueva = st.text_input("Nombre Nueva Marca").upper().strip()
                if st.button("➕ Añadir Marca"):
                    guardar_cambio_google(sh, "CONFIG", "ADD_CONFIG", [nm_nueva, 4])
                    st.toast("Marca añadida"); recargar(); st.rerun()

            with st.expander("🏘️ Gestión de Bodegas"):
                b_sel = st.selectbox("Seleccionar Bodega:", config["depositos"])
                n_nom_b = st.text_input("Nuevo Nombre Bodega").upper().strip()
                c1b, c2b = st.columns(2)
                if c1b.button("📝 Renombrar"):
                    guardar_cambio_google(sh, "CONFIG", "RENAME_CONFIG", [b_sel, n_nom_b, 3])
                    st.toast("Bodega renombrada"); recargar(); st.rerun()
                if c2b.button("🗑️ Eliminar Bodega"):
                    guardar_cambio_google(sh, "CONFIG", "DEL_CONFIG", [b_sel, 3])
                    st.toast("Bodega eliminada"); recargar(); st.rerun()
                st.divider()
                nb_nueva = st.text_input("Nombre Bodega Nueva").upper().strip()
                if st.button("➕ Crear Bodega"):
                    guardar_cambio_google(sh, "CONFIG", "ADD_CONFIG", [nb_nueva, 3])
                    st.toast("Bodega creada"); recargar(); st.rerun()

            if st.button("📜 HISTORIAL", use_container_width=True): st.session_state.ver_historial = True; st.rerun()
            st.download_button("📊 REPORTE EXCEL", generar_excel_reporte(inv), f"Reporte_{datetime.now().strftime('%d_%m')}.xlsx", use_container_width=True)

        if st.button("🔒 Salir", use_container_width=True): 
            st.session_state.edit_mode = False; st.rerun()
