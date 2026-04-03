import streamlit as st
import json
import os
import time
from datetime import datetime

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
    nuevo_log = {"fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "usuario": usuario, "accion": accion, "detalle": detalle}
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

busq = st.text_input("🔍 CÓDIGO:").upper().strip()
if busq:
    res = [v for k, v in inv.items() if (k.split("_", 1)[1] if "_" in k else k) == busq]
    if res:
        for r in res: st.info(f"📍 {r['deposito']} | **{r['marca']}**: {r['stock']} cj")
    else: st.warning("❌ No existe")

st.divider()

if not st.session_state.mostrar_panel:
    if st.button("🚀 ENTRAR AL CONTROL", use_container_width=True, type="primary"):
        st.session_state.mostrar_panel = True
        st.rerun()
else:
    if st.button("⬅️ VOLVER", use_container_width=True):
        st.session_state.mostrar_panel = False
        st.rerun()

if st.session_state.mostrar_panel:
    dep_actual = st.selectbox("📍 Depósito:", config["depositos"])
    tabs = st.tabs(config["marcas"] + ["⚠️ AGOTADOS"])
    
    for i, nombre_tab in enumerate(config["marcas"] + ["⚠️ AGOTADOS"]):
        with tabs[i]:
            if nombre_tab == "⚠️ AGOTADOS":
                items = {k: v for k, v in inv.items() if v.get('stock', 0) == 0 and v.get('deposito') == dep_actual}
            else:
                items = {k: v for k, v in inv.items() if v.get('marca') == nombre_tab and v.get('deposito') == dep_actual and v.get('stock', 0) > 0}
            
            for id_f, info in sorted(items.items()):
                cod_l = id_f.split("_", 1)[1] if "_" in id_f else id_f
                key_id = f"{nombre_tab}_{id_f}"
                
                with st.container(border=True):
                    c1, c2, c3 = st.columns([1.5, 1, 1.8])
                    c1.markdown(f"**{cod_l}**\n<small>{info['marca']}</small>", unsafe_allow_html=True)
                    c2.markdown(f"📦 **{info['stock']}**")
                    
                    if st.session_state.edit_mode:
                        with c3:
                            cant = st.number_input("n", min_value=1, value=1, key=f"n_{key_id}", label_visibility="collapsed")
                            b1, b2, b3 = st.columns(3)
                            
                            if b1.button("➕", key=f"b1_{key_id}"): st.session_state[f"ask_add_{key_id}"] = True
                            if b2.button("➖", key=f"b2_{key_id}", disabled=(info['stock']==0)): st.session_state[f"ask_sub_{key_id}"] = True
                            if b3.button("🗑️", key=f"b3_{key_id}"): st.session_state[f"ask_del_{key_id}"] = True

                            if st.session_state.get(f"ask_add_{key_id}"):
                                if st.button(f"Confirmar +{cant}?", key=f"conf_add_{key_id}", type="primary", use_container_width=True):
                                    inv[id_f]["stock"] += cant
                                    logs = registrar_log(logs, st.session_state.usuario_actual, "SUMA", f"+{cant} {cod_l}")
                                    guardar_todo(inv, config, logs)
                                    del st.session_state[f"ask_add_{key_id}"]; st.rerun()

                            if st.session_state.get(f"ask_sub_{key_id}"):
                                if st.button(f"Confirmar -{cant}?", key=f"conf_sub_{key_id}", type="primary", use_container_width=True):
                                    inv[id_f]["stock"] -= cant
                                    logs = registrar_log(logs, st.session_state.usuario_actual, "RESTA", f"-{cant} {cod_l}")
                                    guardar_todo(inv, config, logs)
                                    del st.session_state[f"ask_sub_{key_id}"]; st.rerun()

                            if st.session_state.get(f"ask_del_{key_id}"):
                                if st.button("🚨 ELIMINAR AHORA", key=f"conf_del_{key_id}", type="primary", use_container_width=True):
                                    del inv[id_f]
                                    guardar_todo(inv, config, logs)
                                    del st.session_state[f"ask_del_{key_id}"]; st.rerun()

with st.sidebar:
    st.header("🔐 Acceso")
    if not st.session_state.edit_mode:
        u_sel = st.selectbox("User", list(config["usuarios"].keys()))
        p_sel = st.text_input("Pass", type="password")
        if st.button("🔓 Entrar", key="btn_login"):
            if config["usuarios"].get(u_sel) == p_sel:
                st.session_state.edit_mode = True
                st.session_state.usuario_actual = u_sel
                st.rerun()
    else:
        st.success(f"👤 {st.session_state.usuario_actual}")
        if st.button("🔒 Salir", key="btn_logout"): st.session_state.edit_mode = False; st.rerun()
        
        st.divider()
        with st.expander("🆕 Nuevo Item"):
            r_mar = st.selectbox("Marca", config["marcas"], key="sel_reg_marca")
            r_cod = st.text_input("Cod", key="in_reg_cod").upper().strip()
            r_dep = st.selectbox("Depo", config["depositos"], key="sel_reg_dep")
            if st.button("💾 Guardar Item", key="btn_reg_save"):
                if r_cod:
                    inv[f"{r_dep}_{r_cod}"] = {"marca": r_mar, "deposito": r_dep, "stock": 0}
                    guardar_todo(inv, config, logs); st.success("OK"); st.rerun()

        if st.session_state.usuario_actual == "ADMIN":
            st.warning("⚡ ADMIN")
            with st.expander("👥 Usuarios"):
                un = st.text_input("Nombre Usuario", key="admin_un").upper()
                up = st.text_input("Clave Usuario", type="password", key="admin_up")
                if st.button("💾 Crear Acceso", key="btn_admin_user"):
                    if un and up:
                        config["usuarios"][un] = up; guardar_todo(inv, config, logs); st.rerun()
            
            with st.expander("🏷️ Marcas"):
                nm = st.text_input("Nombre Nueva Marca", key="admin_nm").upper()
                if st.button("➕ Añadir a Lista", key="btn_admin_brand"):
                    if nm: config["marcas"].append(nm); guardar_todo(inv, config, logs); st.rerun()
                mb = st.selectbox("Borrar Marca Existente", config["marcas"], key="admin_mb")
                if st.button("🗑️ Borrar de Lista", key="btn_admin_del_brand"):
                    config["marcas"].remove(mb); guardar_todo(inv, config, logs); st.rerun()
            
            with st.expander("🏘️ Depósitos"):
                nd = st.text_input("Nombre Nuevo Depo", key="admin_nd").upper()
                if st.button("➕ Crear Depósito", key="btn_admin_depo"):
                    if nd: config["depositos"].append(nd); guardar_todo(inv, config, logs); st.rerun()
            
            with st.expander("📜 Historial"):
                for l in logs: st.write(f"<small>{l['fecha']} - {l['detalle']}</small>", unsafe_allow_html=True)
