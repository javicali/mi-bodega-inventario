import streamlit as st
import json
import os
from datetime import datetime, timedelta

# --- CONFIGURACIÓN DE ARCHIVOS ---
ARCHIVO_DB = "datos_bodega.json"
ARCHIVO_CONF = "config_bodega.json"
ARCHIVO_LOG = "historial_movimientos.json"

def cargar_json(archivo, defecto):
    if os.path.exists(archivo):
        with open(archivo, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: return defecto
    return defecto

def guardar_todo(inv, conf, logs):
    with open(ARCHIVO_DB, "w", encoding="utf-8") as f: json.dump(inv, f, indent=4)
    with open(ARCHIVO_CONF, "w", encoding="utf-8") as f: json.dump(conf, f, indent=4)
    with open(ARCHIVO_LOG, "w", encoding="utf-8") as f: json.dump(logs, f, indent=4)

st.set_page_config(page_title="Bodega Pro", layout="wide")

# Estilos CSS
st.markdown("""<style>
    .block-container {padding-top: 1rem;}
    .stButton>button {padding: 0.2rem 0.5rem; width: 100%;}
</style>""", unsafe_allow_html=True)

inv = cargar_json(ARCHIVO_DB, {})
config = cargar_json(ARCHIVO_CONF, {"usuarios": {"ADMIN": "admin123"}, "depositos": ["SETAR"], "marcas": ["IRUN", "BOOTY", "LEONESA", "YD", "ELT", "HHP", "TMILL"]})
logs = cargar_json(ARCHIVO_LOG, [])

# Estados de sesión
if 'modo_panel' not in st.session_state: st.session_state.modo_panel = False
if 'edit_mode' not in st.session_state: st.session_state.edit_mode = False
if 'ver_stock_general' not in st.session_state: st.session_state.ver_stock_general = False

# --- FUNCIONES DE TARJETAS ---
def mostrar_item_lectura(id_f, info):
    cod_l = id_f.split("_", 1)[1] if "_" in id_f else id_f
    with st.container(border=True):
        c1, c2 = st.columns([2, 1])
        c1.markdown(f"**{cod_l}**\n<small>{info['marca']} | {info['deposito']}</small>", unsafe_allow_html=True)
        txt_u = "caja" if info['stock'] == 1 else "cajas"
        c2.markdown(f"📦 **{info['stock']}**\n<small>{txt_u}</small>", unsafe_allow_html=True)

def mostrar_item_edicion(id_f, info, sufijo):
    cod_l = id_f.split("_", 1)[1] if "_" in id_f else id_f
    with st.container(border=True):
        c1, c2, c3 = st.columns([1.5, 1, 2.2])
        c1.markdown(f"**{cod_l}**\n<small>{info['marca']} | {info['deposito']}</small>", unsafe_allow_html=True)
        txt_u = "caja" if info['stock'] == 1 else "cajas"
        c2.markdown(f"📦 **{info['stock']}**\n<small>{txt_u}</small>", unsafe_allow_html=True)
        
        with c3:
            # Widget de número (sin intentar resetearlo manualmente por código)
            cant = st.number_input("n", min_value=1, value=1, key=f"n_{sufijo}_{id_f}", label_visibility="collapsed")
            col_btn = st.columns(3)
            if col_btn[0].button("➕", key=f"add_{sufijo}_{id_f}"): st.session_state[f"conf_{sufijo}_{id_f}"] = "S"
            if col_btn[1].button("➖", key=f"sub_{sufijo}_{id_f}", disabled=info['stock']==0): st.session_state[f"conf_{sufijo}_{id_f}"] = "R"
            if col_btn[2].button("🗑️", key=f"del_{sufijo}_{id_f}"): st.session_state[f"conf_{sufijo}_{id_f}"] = "B"

            # Lógica de confirmación
            key_confirmacion = f"conf_{sufijo}_{id_f}"
            estado = st.session_state.get(key_confirmacion)
            
            if estado:
                if st.button("CONFIRMAR OK", key=f"btn_ok_{sufijo}_{id_f}", type="primary"):
                    if estado == "S": inv[id_f]["stock"] += cant
                    elif estado == "R": inv[id_f]["stock"] -= cant
                    elif estado == "B": 
                        if id_f in inv: del inv[id_f]
                    
                    guardar_todo(inv, config, logs)
                    # Limpiamos solo el estado de confirmación
                    del st.session_state[key_confirmacion]
                    st.rerun()

# --- LÓGICA DE INTERFAZ ---

if not st.session_state.modo_panel:
    st.title("🏢 Consulta de Inventario")
    
    st.subheader("🔍 Buscar por Código")
    c1, c2 = st.columns([4, 1])
    with c1:
        busq = st.text_input("Ingrese el código:", placeholder="Ej: 501...", key="search_main").upper().strip()
    with c2:
        st.write("##")
        btn_l = st.button("🔍 Buscar", key="btn_search_main")
    
    if busq:
        encontrados = {k: v for k, v in inv.items() if (k.split("_", 1)[1] if "_" in k else k) == busq}
        if encontrados:
            for id_f, info in encontrados.items():
                st.info(f"✅ **{busq}** ({info['marca']}) en **{info['deposito']}**: {info['stock']} cajas")
        elif btn_l: st.error("Código no encontrado.")

    st.divider()

    st.subheader("📦 Vista General de Stock")
    if not st.session_state.ver_stock_general:
        if st.button("👁️ MOSTRAR TODO EL INVENTARIO"):
            st.session_state.ver_stock_general = True
            st.rerun()
    else:
        if st.button("🚫 OCULTAR INVENTARIO"):
            st.session_state.ver_stock_general = False
            st.rerun()
        
        dep_v = st.selectbox("Seleccione Depósito:", config["depositos"], key="sel_dep_view")
        tab_v = st.tabs(config["marcas"])
        for i, m_nom in enumerate(config["marcas"]):
            with tab_v[i]:
                items_v = {k: v for k, v in inv.items() if v.get('marca') == m_nom and v.get('deposito') == dep_v and v.get('stock', 0) > 0}
                if items_v:
                    for id_f, info in sorted(items_v.items()): mostrar_item_lectura(id_f, info)
                else: st.write("Sin existencias.")

else:
    st.title("🛠️ Panel de Modificación")
    st.info(f"Sesión activa: **{st.session_state.get('usuario_actual', 'Admin')}**")
    
    busq_m = st.text_input("🔎 BUSCAR CÓDIGO PARA EDITAR:", placeholder="Código...", key="search_edit").upper().strip()

    if busq_m:
        items_f = {k: v for k, v in inv.items() if (k.split("_", 1)[1] if "_" in k else k) == busq_m}
        if items_f:
            for id_f, info in items_f.items(): mostrar_item_edicion(id_f, info, "busq")
        else: st.error("No encontrado.")
    else:
        dep_sel = st.selectbox("📍 Depósito de Trabajo:", config["depositos"], key="sel_dep_edit")
        tabs_e = st.tabs(config["marcas"] + ["⚠️ AGOTADOS"])
        for i, m_e in enumerate(config["marcas"] + ["⚠️ AGOTADOS"]):
            with tabs_e[i]:
                if m_e == "⚠️ AGOTADOS":
                    items = {k: v for k, v in inv.items() if v.get('stock', 0) == 0 and v.get('deposito') == dep_sel}
                else:
                    items = {k: v for k, v in inv.items() if v.get('marca') == m_e and v.get('deposito') == dep_sel and v.get('stock', 0) > 0}
                for id_f, info in sorted(items.items()): mostrar_item_edicion(id_f, info, "tab")

# --- SIDEBAR (SISTEMA DE ACCESO) ---
with st.sidebar:
    st.header("🔐 Acceso Privado")
    if not st.session_state.edit_mode:
        u = st.selectbox("Usuario", list(config["usuarios"].keys()), key="user_sel")
        p = st.text_input("Clave", type="password", key="pass_input")
        if st.button("🔓 Desbloquear"):
            if config["usuarios"].get(u) == p:
                st.session_state.edit_mode = True
                st.session_state.usuario_actual = u
                st.rerun()
    else:
        st.success(f"👤 {st.session_state.usuario_actual}")
        
        if not st.session_state.modo_panel:
            if st.button("⚙️ ABRIR PANEL DE CONTROL"):
                st.session_state.modo_panel = True
                st.rerun()
        else:
            if st.button("🏠 IR A VISTA PÚBLICA"):
                st.session_state.modo_panel = False
                st.rerun()
        
        st.divider()
        if st.button("🔒 CERRAR SESIÓN"):
            st.session_state.edit_mode = False
            st.session_state.modo_panel = False
            st.rerun()
            
        if st.session_state.edit_mode:
            with st.expander("🆕 Registrar Nuevo Item"):
                rm = st.selectbox("Marca", config["marcas"], key="reg_marca")
                rc = st.text_input("Código", key="reg_cod").upper().strip()
                rd = st.selectbox("Depósito", config["depositos"], key="reg_dep")
                if st.button("💾 Guardar"):
                    if rc:
                        inv[f"{rd}_{rc}"] = {"marca": rm, "deposito": rd, "stock": 0}
                        guardar_todo(inv, config, logs)
                        st.rerun()
