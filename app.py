import streamlit as st
import json
import os
import time
from datetime import datetime, timedelta

# Archivos de base de datos
ARCHIVO_DB = "datos_bodega.json"
ARCHIVO_CONF = "config_bodega.json"
ARCHIVO_LOG = "historial_movimientos.json"

def cargar_json(archivo, defecto):
    if os.path.exists(archivo):
        with open(archivo, "r", encoding="utf-8") as f:
            try: 
                data = json.load(f)
                if archivo == ARCHIVO_CONF:
                    if "usuarios" not in data: data["usuarios"] = {"ADMIN": "admin123"}
                    if "depositos" not in data: data["depositos"] = ["SETAR"]
                    if "marcas" not in data: data["marcas"] = ["IRUN", "BOOTY", "LEONESA", "YD", "ELT", "HHP", "TMILL"]
                return data
            except: return defecto
    return defecto

def guardar_todo(inv, conf, logs):
    with open(ARCHIVO_DB, "w", encoding="utf-8") as f: json.dump(inv, f, indent=4)
    with open(ARCHIVO_CONF, "w", encoding="utf-8") as f: json.dump(conf, f, indent=4)
    with open(ARCHIVO_LOG, "w", encoding="utf-8") as f: json.dump(logs, f, indent=4)

def registrar_log(logs, usuario, accion, detalle):
    hora_correcta = datetime.now() - timedelta(hours=4)
    nuevo_log = {"fecha": hora_correcta.strftime("%d/%m/%Y %H:%M"), "usuario": usuario, "accion": accion, "detalle": detalle}
    logs.insert(0, nuevo_log)
    return logs[:200]

st.set_page_config(page_title="Bodega Pro", layout="wide")

st.markdown("""<style>
    .block-container {padding-top: 1rem; padding-bottom: 0rem;}
    .stButton>button {padding: 0.2rem 0.5rem;}
</style>""", unsafe_allow_html=True)

inv = cargar_json(ARCHIVO_DB, {})
config = cargar_json(ARCHIVO_CONF, {})
logs = cargar_json(ARCHIVO_LOG, [])

if 'edit_mode' not in st.session_state: st.session_state.edit_mode = False
if 'mostrar_panel' not in st.session_state: st.session_state.mostrar_panel = False
if 'usuario_actual' not in st.session_state: st.session_state.usuario_actual = ""

st.title("🏢 Inventario")

# --- BUSCADOR PÚBLICO (SOLO LECTURA) ---
c_bus1, c_bus2 = st.columns([4, 1])
with c_bus1:
    busq_pub = st.text_input("Consultar Stock:", key="in_pub", placeholder="Código...").upper().strip()
with c_bus2:
    st.write("##")
    btn_pub = st.button("🔍", key="btn_pub", type="primary")

if busq_pub and (btn_pub or st.session_state.get('l_pub') != busq_pub):
    st.session_state['l_pub'] = busq_pub
    res = [v for k, v in inv.items() if (k.split("_", 1)[1] if "_" in k else k) == busq_pub]
    if res:
        for r in res: st.info(f"📍 {r['deposito']} | **{r['marca']}**: {r['stock']} cajas")
    else: st.error("❌ No existe")

st.divider()

# --- BOTÓN DE ENTRADA / SALIDA ---
if not st.session_state.mostrar_panel:
    if st.button("🚀 ENTRAR AL CONTROL", use_container_width=True, type="primary"):
        st.session_state.mostrar_panel = True
        st.rerun()
else:
    if st.button("⬅️ VOLVER AL INICIO", use_container_width=True):
        st.session_state.mostrar_panel = False
        st.rerun()

# --- PANEL DE CONTROL ---
if st.session_state.mostrar_panel:
    st.subheader("🛠️ Panel de Modificación")
    
    # BUSCADOR DENTRO DEL PANEL PARA MODIFICAR RÁPIDO
    c_mod1, c_mod2 = st.columns([4, 1])
    with c_mod1:
        busq_mod = st.text_input("BUSCAR PARA EDITAR:", key="in_mod", placeholder="Escribe el código a modificar...").upper().strip()
    with c_mod2:
        st.write("##")
        btn_mod = st.button("🔎", key="btn_mod")

    if busq_mod:
        items_edit = {k: v for k, v in inv.items() if (k.split("_", 1)[1] if "_" in k else k) == busq_mod}
        if items_edit:
            for id_f, info in items_edit.items():
                with st.container(border=True):
                    st.write(f"✏️ Editando: **{busq_mod}** ({info['marca']}) en **{info['deposito']}**")
                    col1, col2 = st.columns([1, 2])
                    col1.metric("Stock Actual", f"{info['stock']} cj")
                    
                    if st.session_state.edit_mode:
                        with col2:
                            n_cant = st.number_input("Cantidad", min_value=1, value=1, key=f"edit_n_{id_f}")
                            b_add, b_sub, b_del = st.columns(3)
                            if b_add.button("➕", key=f"edit_add_{id_f}"):
                                inv[id_f]["stock"] += n_cant
                                logs = registrar_log(logs, st.session_state.usuario_actual, "SUMA", f"+{n_cant} {busq_mod}")
                                guardar_todo(inv, config, logs); st.rerun()
                            if b_sub.button("➖", key=f"edit_sub_{id_f}", disabled=info['stock']<n_cant):
                                inv[id_f]["stock"] -= n_cant
                                logs = registrar_log(logs, st.session_state.usuario_actual, "RESTA", f"-{n_cant} {busq_mod}")
                                guardar_todo(inv, config, logs); st.rerun()
                            if b_del.button("🗑️", key=f"edit_del_{id_f}"):
                                del inv[id_f]
                                logs = registrar_log(logs, st.session_state.usuario_actual, "BORRAR", f"Eliminó {busq_mod}")
                                guardar_todo(inv, config, logs); st.rerun()
                    else:
                        st.warning("Inicia sesión en la barra lateral para modificar.")
        elif btn_mod:
            st.error("Código no encontrado para editar.")

    st.divider()
    
    # VISTA POR DEPÓSITOS Y TABS (Lo que ya tenías antes)
    dep_actual = st.selectbox("📍 Ver por Depósito:", config["depositos"], key="sel_dep")
    tabs = st.tabs(config["marcas"] + ["⚠️ AGOTADOS"])
    
    for i, nombre_tab in enumerate(config["marcas"] + ["⚠️ AGOTADOS"]):
        with tabs[i]:
            if nombre_tab == "⚠️ AGOTADOS":
                items = {k: v for k, v in inv.items() if v.get('stock', 0) == 0 and v.get('deposito') == dep_actual}
            else:
                items = {k: v for k, v in inv.items() if v.get('marca') == nombre_tab and v.get('deposito') == dep_actual and v.get('stock', 0) > 0}
            
            for id_f, info in sorted(items.items()):
                cod_l = id_f.split("_", 1)[1] if "_" in id_f else id_f
                with st.container(border=True):
                    c1, c2, c3 = st.columns([1.5, 1, 1.8])
                    c1.markdown(f"**{cod_l}**\n<small>{info['marca']}</small>", unsafe_allow_html=True)
                    c2.markdown(f"📦 **{info['stock']}**")
                    if st.session_state.edit_mode:
                        with c3:
                            cant = st.number_input("n", min_value=1, value=1, key=f"n_{id_f}", label_visibility="collapsed")
                            b1, b2, b3 = st.columns(3)
                            if b1.button("➕", key=f"b1_{id_f}"):
                                inv[id_f]["stock"] += cant
                                logs = registrar_log(logs, st.session_state.usuario_actual, "SUMA", f"+{cant} {cod_l}")
                                guardar_todo(inv, config, logs); st.rerun()
                            if b2.button("➖", key=f"b2_{id_f}", disabled=info['stock']==0):
                                inv[id_f]["stock"] -= cant
                                logs = registrar_log(logs, st.session_state.usuario_actual, "RESTA", f"-{cant} {cod_l}")
                                guardar_todo(inv, config, logs); st.rerun()
                            if b3.button("🗑️", key=f"b3_{id_f}"):
                                del inv[id_f]
                                guardar_todo(inv, config, logs); st.rerun()

# --- SIDEBAR (USUARIOS Y ADMIN) ---
with st.sidebar:
    st.header("🔐 Acceso")
    if not st.session_state.edit_mode:
        u_sel = st.selectbox("Usuario", list(config["usuarios"].keys()), key="sb_u")
        p_sel = st.text_input("Clave", type="password", key="sb_p")
        if st.button("🔓 Entrar"):
            if config["usuarios"].get(u_sel) == p_sel:
                st.session_state.edit_mode = True
                st.session_state.usuario_actual = u_sel
                st.rerun()
    else:
        st.success(f"👤 {st.session_state.usuario_actual}")
        if st.button("🔒 Salir"): st.session_state.edit_mode = False; st.rerun()
        
        st.divider()
        with st.expander("🆕 Registrar Nuevo Item"):
            rm = st.selectbox("Marca", config["marcas"], key="reg_m")
            rc = st.text_input("Código", key="reg_c").upper().strip()
            rd = st.selectbox("Depósito", config["depositos"], key="reg_d")
            if st.button("💾 Guardar Item"):
                if rc:
                    inv[f"{rd}_{rc}"] = {"marca": rm, "deposito": rd, "stock": 0}
                    logs = registrar_log(logs, st.session_state.usuario_actual, "CREACIÓN", f"Nuevo: {rc}")
                    guardar_todo(inv, config, logs); st.rerun()

        if st.session_state.usuario_actual == "ADMIN":
            st.warning("⚡ PANEL ADMIN")
            with st.expander("👥 Usuarios"):
                un = st.text_input("Nombre", key="adm_un").upper()
                up = st.text_input("Clave", type="password", key="adm_up")
                if st.button("💾 Guardar Usuario"):
                    if un and up: config["usuarios"][un] = up; guardar_todo(inv, config, logs); st.rerun()
            with st.expander("🏘️ Depósitos y Traslados"):
                nd = st.text_input("Nuevo Depósito").upper()
                if st.button("➕ Crear Depo"):
                    if nd and nd not in config["depositos"]: config["depositos"].append(nd); guardar_todo(inv, config, logs); st.rerun()
            with st.expander("📜 Historial"):
                for l in logs: st.write(f"**{l['fecha']}** | 👤 {l.get('usuario','?')}: {l['detalle']}")
