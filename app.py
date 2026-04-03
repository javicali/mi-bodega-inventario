import streamlit as st
import json
import os
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

# CSS para botones compactos
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

# --- BUSCADOR PÚBLICO (INICIO) ---
if not st.session_state.mostrar_panel:
    c_bus1, c_bus2 = st.columns([4, 1])
    with c_bus1:
        busq_pub = st.text_input("Consultar Stock:", key="in_pub", placeholder="Código...").upper().strip()
    with c_bus2:
        st.write("##")
        btn_pub = st.button("🔍", key="btn_pub", type="primary")

    if busq_pub:
        res = [v for k, v in inv.items() if (k.split("_", 1)[1] if "_" in k else k) == busq_pub]
        if res:
            for r in res:
                txt = "caja" if r['stock'] == 1 else "cajas"
                st.info(f"📍 {r['deposito']} | **{r['marca']}**: {r['stock']} {txt}")
        elif btn_pub: st.error("❌ No existe")

st.divider()

# --- BOTÓN DE NAVEGACIÓN ---
if not st.session_state.mostrar_panel:
    if st.button("🚀 ENTRAR AL CONTROL", use_container_width=True, type="primary"):
        st.session_state.mostrar_panel = True
        st.rerun()
else:
    if st.button("⬅️ VOLVER AL INICIO", use_container_width=True):
        st.session_state.mostrar_panel = False
        st.rerun()

# --- PANEL DE CONTROL (MODO EDICIÓN) ---
if st.session_state.mostrar_panel:
    st.subheader("🛠️ Gestión de Mercadería")
    
    # Buscador Único de Edición
    busq_mod = st.text_input("🔍 BUSCAR CÓDIGO ESPECÍFICO:", key="in_mod", placeholder="Escribe para filtrar...").upper().strip()

    def mostrar_tarjeta(id_f, info):
        cod_l = id_f.split("_", 1)[1] if "_" in id_f else id_f
        with st.container(border=True):
            c1, c2, c3 = st.columns([1.5, 1, 1.8])
            c1.markdown(f"**{cod_l}**\n<small>{info['marca']} | {info['deposito']}</small>", unsafe_allow_html=True)
            txt_t = "caja" if info['stock'] == 1 else "cajas"
            c2.markdown(f"📦 **{info['stock']}**\n<small>{txt_t}</small>", unsafe_allow_html=True)
            
            if st.session_state.edit_mode:
                with c3:
                    cant = st.number_input("n", min_value=1, value=1, key=f"n_{id_f}", label_visibility="collapsed")
                    b1, b2, b3 = st.columns(3)
                    if b1.button("➕", key=f"add_{id_f}"): st.session_state[f"confirm_{id_f}"] = "SUMA"
                    if b2.button("➖", key=f"sub_{id_f}", disabled=info['stock']==0): st.session_state[f"confirm_{id_f}"] = "RESTA"
                    if b3.button("🗑️", key=f"del_{id_f}"): st.session_state[f"confirm_{id_f}"] = "BORRAR"

                    # Lógica de confirmación única
                    conf_tipo = st.session_state.get(f"confirm_{id_f}")
                    if conf_tipo:
                        if conf_tipo == "SUMA":
                            if st.button(f"CONFIRMAR +{cant}?", key=f"ok_a_{id_f}", type="primary"):
                                inv[id_f]["stock"] += cant
                                registrar_log(logs, st.session_state.usuario_actual, "SUMA", f"+{cant} {cod_l}")
                                guardar_todo(inv, config, logs); del st.session_state[f"confirm_{id_f}"]; st.rerun()
                        elif conf_tipo == "RESTA":
                            if st.button(f"CONFIRMAR -{cant}?", key=f"ok_s_{id_f}", type="primary"):
                                inv[id_f]["stock"] -= cant
                                registrar_log(logs, st.session_state.usuario_actual, "RESTA", f"-{cant} {cod_l}")
                                guardar_todo(inv, config, logs); del st.session_state[f"confirm_{id_f}"]; st.rerun()
                        elif conf_tipo == "BORRAR":
                            if st.button("🚨 ¿ELIMINAR?", key=f"ok_d_{id_f}", type="primary"):
                                del inv[id_f]
                                registrar_log(logs, st.session_state.usuario_actual, "BORRAR", f"Eliminó {cod_l}")
                                guardar_todo(inv, config, logs); del st.session_state[f"confirm_{id_f}"]; st.rerun()
            else:
                c3.warning("🔒 Loguéate")

    if busq_mod:
        # Solo mostrar resultados de búsqueda
        items_edit = {k: v for k, v in inv.items() if (k.split("_", 1)[1] if "_" in k else k) == busq_mod}
        if items_edit:
            for id_f, info in items_edit.items(): mostrar_tarjeta(id_f, info)
        else: st.error("Código no encontrado.")
    else:
        # Si no hay búsqueda, mostrar las pestañas normales
        dep_actual = st.selectbox("📍 Depósito:", config["depositos"], key="sel_dep")
        tabs = st.tabs(config["marcas"] + ["⚠️ AGOTADOS"])
        for i, nombre_tab in enumerate(config["marcas"] + ["⚠️ AGOTADOS"]):
            with tabs[i]:
                if nombre_tab == "⚠️ AGOTADOS":
                    items = {k: v for k, v in inv.items() if v['stock'] == 0 and v['deposito'] == dep_actual}
                else:
                    items = {k: v for k, v in inv.items() if v['marca'] == nombre_tab and v['deposito'] == dep_actual and v['stock'] > 0}
                
                for id_f, info in sorted(items.items()):
                    mostrar_tarjeta(id_f, info)

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔐 Acceso")
    if not st.session_state.edit_mode:
        u_sel = st.selectbox("Usuario", list(config["usuarios"].keys()))
        p_sel = st.text_input("Clave", type="password")
        if st.button("🔓 Entrar"):
            if config["usuarios"].get(u_sel) == p_sel:
                st.session_state.edit_mode, st.session_state.usuario_actual = True, u_sel
                st.rerun()
    else:
        st.success(f"👤 {st.session_state.usuario_actual}")
        if st.button("🔒 Salir"): st.session_state.edit_mode = False; st.rerun()
        st.divider()
        with st.expander("🆕 Registrar Nuevo"):
            rm = st.selectbox("Marca", config["marcas"])
            rc = st.text_input("Código").upper().strip()
            rd = st.selectbox("Depósito", config["depositos"])
            if st.button("💾 Guardar"):
                if rc:
                    inv[f"{rd}_{rc}"] = {"marca": rm, "deposito": rd, "stock": 0}
                    registrar_log(logs, st.session_state.usuario_actual, "CREACIÓN", f"Nuevo: {rc}")
                    guardar_todo(inv, config, logs); st.rerun()
        if st.session_state.usuario_actual == "ADMIN":
            with st.expander("📜 Historial"):
                for l in logs: st.write(f"**{l['fecha']}** | {l['usuario']}: {l['detalle']}")
