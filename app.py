
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

if 'mostrar_panel' not in st.session_state: st.session_state.edit_mode = False # Para control de navegación
if 'ver_stock_general' not in st.session_state: st.session_state.ver_stock_general = False

# --- FUNCIÓN TARJETA (LECTURA) ---
def mostrar_item_lectura(id_f, info):
    cod_l = id_f.split("_", 1)[1] if "_" in id_f else id_f
    with st.container(border=True):
        c1, c2 = st.columns([2, 1])
        c1.markdown(f"**{cod_l}**\n<small>{info['marca']} | {info['deposito']}</small>", unsafe_allow_html=True)
        txt_u = "caja" if info['stock'] == 1 else "cajas"
        c2.markdown(f"📦 **{info['stock']}**\n<small>{txt_u}</small>", unsafe_allow_html=True)

# --- FUNCIÓN TARJETA (EDICIÓN) ---
def mostrar_item_edicion(id_f, info, sufijo):
    cod_l = id_f.split("_", 1)[1] if "_" in id_f else id_f
    with st.container(border=True):
        c1, c2, c3 = st.columns([1.5, 1, 2.2])
        c1.markdown(f"**{cod_l}**\n<small>{info['marca']} | {info['deposito']}</small>", unsafe_allow_html=True)
        txt_u = "caja" if info['stock'] == 1 else "cajas"
        c2.markdown(f"📦 **{info['stock']}**\n<small>{txt_u}</small>", unsafe_allow_html=True)
        
        if st.session_state.get('edit_mode', False):
            with c3:
                cant = st.number_input("n", min_value=1, value=1, key=f"n_{sufijo}_{id_f}", label_visibility="collapsed")
                col_btn = st.columns(3)
                if col_btn[0].button("➕", key=f"add_{sufijo}_{id_f}"): st.session_state[f"conf_{sufijo}_{id_f}"] = "S"
                if col_btn[1].button("➖", key=f"sub_{sufijo}_{id_f}", disabled=info['stock']==0): st.session_state[f"conf_{sufijo}_{id_f}"] = "R"
                if col_btn[2].button("🗑️", key=f"del_{sufijo}_{id_f}"): st.session_state[f"conf_{sufijo}_{id_f}"] = "B"

                estado = st.session_state.get(f"conf_{sufijo}_{id_f}")
                if estado:
                    if st.button("OK?", key=f"ok_{sufijo}_{id_f}", type="primary"):
                        if estado == "S": inv[id_f]["stock"] += cant
                        elif estado == "R": inv[id_f]["stock"] -= cant
                        elif estado == "B": del inv[id_f]
                        guardar_todo(inv, config, logs)
                        if f"n_{sufijo}_{id_f}" in st.session_state: st.session_state[f"n_{sufijo}_{id_f}"] = 1
                        del st.session_state[f"conf_{sufijo}_{id_f}"]
                        st.rerun()

# --- INTERFAZ PRINCIPAL ---

if not st.session_state.get('mostrar_panel', False):
    st.title("🏢 Sistema de Bodega")
    
    # 1. BUSCADOR RÁPIDO
    st.subheader("🔍 Consulta Rápida")
    c1, c2 = st.columns([4, 1])
    with c1:
        busq = st.text_input("Ingrese código:", placeholder="Escriba código...").upper().strip()
    with c2:
        st.write("##")
        btn_l = st.button("🔍 Buscar")
    
    if busq:
        encontrados = {k: v for k, v in inv.items() if (k.split("_", 1)[1] if "_" in k else k) == busq}
        if encontrados:
            for id_f, info in encontrados.items():
                st.info(f"✅ **{busq}** ({info['marca']}) en **{info['deposito']}**: {info['stock']} cajas")
        elif btn_l: st.error("No existe.")

    st.divider()

    # 2. VISTA GENERAL CON BOTÓN
    st.subheader("📦 Inventario General")
    if not st.session_state.ver_stock_general:
        if st.button("👁️ VER TODO EL STOCK", type="secondary"):
            st.session_state.ver_stock_general = True
            st.rerun()
    else:
        if st.button("🚫 OCULTAR STOCK"):
            st.session_state.ver_stock_general = False
            st.rerun()
        
        dep_v = st.selectbox("Seleccione Depósito:", config["depositos"])
        tab_v = st.tabs(config["marcas"])
        for i, m_nom in enumerate(config["marcas"]):
            with tab_v[i]:
                items_v = {k: v for k, v in inv.items() if v['marca'] == m_nom and v['deposito'] == dep_v and v['stock'] > 0}
                if items_v:
                    for id_f, info in sorted(items_v.items()): mostrar_item_lectura(id_f, info)
                else: st.write("Sin existencias.")

    # 3. ACCESO AL PANEL
    st.write("---")
    if st.button("⚙️ ENTRAR AL CONTROLADOR", use_container_width=True):
        st.session_state.mostrar_panel = True
        st.rerun()

else:
    # --- PANEL DE CONTROL (MODIFICACIÓN) ---
    st.title("🛠️ Panel de Modificación")
    if st.button("⬅️ VOLVER AL INICIO"):
        st.session_state.mostrar_panel = False
        st.rerun()
    
    st.divider()
    busq_m = st.text_input("🔎 BUSCAR PARA EDITAR:", placeholder="Código...").upper().strip()

    if busq_m:
        items_f = {k: v for k, v in inv.items() if (k.split("_", 1)[1] if "_" in k else k) == busq_m}
        if items_f:
            for id_f, info in items_f.items(): mostrar_item_edicion(id_f, info, "busq")
        else: st.error("No encontrado.")
    else:
        dep_sel = st.selectbox("📍 Depósito Actual:", config["depositos"])
        tabs_e = st.tabs(config["marcas"] + ["⚠️ AGOTADOS"])
        for i, m_e in enumerate(config["marcas"] + ["⚠️ AGOTADOS"]):
            with tabs_e[i]:
                if m_e == "⚠️ AGOTADOS":
                    items = {k: v for k, v in inv.items() if v['stock'] == 0 and v['deposito'] == dep_sel}
                else:
                    items = {k: v for k, v in inv.items() if v['marca'] == m_e and v['deposito'] == dep_sel and v['stock'] > 0}
                for id_f, info in sorted(items.items()): mostrar_item_edicion(id_f, info, "tab")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔐 Acceso")
    if not st.session_state.get('edit_mode', False):
        u = st.selectbox("Usuario", list(config["usuarios"].keys()))
        p = st.text_input("Clave", type="password")
        if st.button("🔓 Desbloquear"):
            if config["usuarios"].get(u) == p:
                st.session_state.edit_mode = True
                st.session_state.usuario_actual = u
                st.rerun()
    else:
        st.success(f"👤 {st.session_state.usuario_actual}")
        if st.button("🔒 Bloquear"): st.session_state.edit_mode = False; st.rerun()
        st.divider()
        with st.expander("🆕 Registrar Nuevo"):
            rm = st.selectbox("Marca", config["marcas"])
            rc = st.text_input("Código").upper().strip()
            rd = st.selectbox("Depósito", config["depositos"])
            if st.button("💾 Guardar"):
                if rc:
                    inv[f"{rd}_{rc}"] = {"marca": rm, "deposito": rd, "stock": 0}
                    guardar_todo(inv, config, logs); st.rerun()
