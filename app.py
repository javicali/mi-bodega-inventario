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

st.set_page_config(page_title="Bodega Master Pro", layout="wide")

if 'edit_mode' not in st.session_state: st.session_state.edit_mode = False
if 'usuario_actual' not in st.session_state: st.session_state.usuario_actual = ""
if 'mostrar_panel' not in st.session_state: st.session_state.mostrar_panel = False

inv = cargar_json(ARCHIVO_DB, {})
config = cargar_json(ARCHIVO_CONF, {})
logs = cargar_json(ARCHIVO_LOG, [])

st.title("🏢 Gestión de Inventario")

# --- BUSCADOR EXACTO ---
busq = st.text_input("🔍 BUSCAR CÓDIGO EXACTO:").upper().strip()
if busq:
    res = []
    for k, v in inv.items():
        codigo_en_db = k.split("_", 1)[1] if "_" in k else k
        if codigo_en_db == busq:
            res.append(v)
    
    if res:
        cols = st.columns(4)
        for i, r in enumerate(res):
            with cols[i%4]: st.info(f"📍 {r['deposito']}\n\n**{r['marca']}**\n\nStock: {r['stock']} cajas")
    else:
        st.warning(f"❌ CÓDIGO NO EXISTENTE: '{busq}'")

st.divider()

if not st.session_state.mostrar_panel:
    if st.button("🚀 ENTRAR AL CONTROL POR DEPÓSITO", use_container_width=True, type="primary"):
        st.session_state.mostrar_panel = True
        st.rerun()
else:
    if st.button("⬅️ VOLVER AL INICIO", use_container_width=True):
        st.session_state.mostrar_panel = False
        st.rerun()

if st.session_state.mostrar_panel:
    st.subheader("📦 Control de Cajas")
    dep_actual = st.selectbox("📍 Depósito Actual:", config["depositos"], key="dep_main_sel")
    
    lista_pestanas = config["marcas"] + ["⚠️ AGOTADOS"]
    tabs = st.tabs(lista_pestanas)
    
    for i, nombre_tab in enumerate(lista_pestanas):
        with tabs[i]:
            if nombre_tab == "⚠️ AGOTADOS":
                items_mostrar = {k: v for k, v in inv.items() if v.get('stock', 0) == 0 and v.get('deposito') == dep_actual}
            else:
                items_mostrar = {k: v for k, v in inv.items() if v.get('marca') == nombre_tab and v.get('deposito') == dep_actual and v.get('stock', 0) > 0}
            
            for id_f, info in sorted(items_mostrar.items()):
                cod_l = id_f.split("_", 1)[1] if "_" in id_f else id_f
                with st.container(border=True):
                    c_txt, c_stk, c_act = st.columns([1, 1, 2])
                    c_txt.markdown(f"### {cod_l}\n**Marca: {info['marca']}**")
                    c_stk.metric("Stock Actual", f"{info['stock']} cajas")
                    
                    if st.session_state.edit_mode:
                        with c_act:
                            cant = st.number_input(f"Cantidad", min_value=1, value=1, key=f"input_{id_f}")
                            col_b1, col_b2, col_del = st.columns([1, 1, 1])
                            
                            if col_b1.button(f"➕ Sumar", key=f"btn_add_{id_f}", use_container_width=True):
                                st.session_state[f"conf_add_{id_f}"] = True
                            if col_b2.button(f"➖ Restar", key=f"btn_sub_{id_f}", use_container_width=True, disabled=(info['stock'] == 0)):
                                st.session_state[f"conf_sub_{id_f}"] = True
                            if col_del.button("🗑️ Eliminar", key=f"btn_del_{id_f}", use_container_width=True):
                                st.session_state[f"conf_del_{id_f}"] = True

                            if st.session_state.get(f"conf_add_{id_f}"):
                                if st.button("✅ CONFIRMAR SUMA", key=f"real_add_{id_f}", type="primary"):
                                    inv[id_f]["stock"] += cant
                                    logs = registrar_log(logs, st.session_state.usuario_actual, "INGRESO", f"{cant} {info['marca']} {cod_l}")
                                    guardar_todo(inv, config, logs)
                                    st.session_state[f"conf_add_{id_f}"] = False
                                    st.rerun()

                            if st.session_state.get(f"conf_sub_{id_f}"):
                                if st.button("✅ CONFIRMAR RESTA", key=f"real_sub_{id_f}", type="primary"):
                                    inv[id_f]["stock"] -= cant
                                    logs = registrar_log(logs, st.session_state.usuario_actual, "SALIDA", f"{cant} {info['marca']} {cod_l}")
                                    guardar_todo(inv, config, logs)
                                    st.session_state[f"conf_sub_{id_f}"] = False
                                    st.rerun()

                            if st.session_state.get(f"conf_del_{id_f}"):
                                if st.button("🚨 SÍ, ELIMINAR", key=f"real_del_{id_f}", type="primary"):
                                    del inv[id_f]
                                    guardar_todo(inv, config, logs)
                                    st.session_state[f"conf_del_{id_f}"] = False
                                    st.rerun()
                                if st.button("CANCELAR", key=f"can_del_{id_f}"):
                                    st.session_state[f"conf_del_{id_f}"] = False
                                    st.rerun()

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔐 Acceso")
    if not st.session_state.edit_mode:
        u_sel = st.selectbox("Usuario", list(config["usuarios"].keys()))
        p_sel = st.text_input("Contraseña", type="password")
        if st.button("🔓 Desbloquear"):
            if config["usuarios"].get(u_sel) == p_sel:
                st.session_state.edit_mode = True
                st.session_state.usuario_actual = u_sel
                st.rerun()
    else:
        st.success(f"👤 {st.session_state.usuario_actual}")
        if st.button("🔒 Cerrar Sesión"):
            st.session_state.edit_mode = False
            st.rerun()
        
        st.divider()
        with st.expander("🆕 Registrar Nuevo Item"):
            reg_mar = st.selectbox("Marca", config["marcas"])
            reg_cod = st.text_input("Código Item").upper().strip()
            reg_dep = st.selectbox("Depósito Destino", config["depositos"])
            if st.button("💾 Guardar Item"):
                if reg_cod:
                    id_f = f"{reg_dep}_{reg_cod}"
                    inv[id_f] = {"marca": reg_mar, "deposito": reg_dep, "stock": 0}
                    logs = registrar_log(logs, st.session_state.usuario_actual, "CREACIÓN", f"{reg_mar} {reg_cod}")
                    guardar_todo(inv, config, logs)
                    st.success(f"✅ {reg_cod} creado")
                    time.sleep(0.5); st.rerun()

        if st.session_state.usuario_actual == "ADMIN":
            st.divider()
            st.warning("⚡ PANEL ADMIN")
            
            with st.expander("👥 1. Usuarios"):
                nu_n = st.text_input("Nombre Usuario").upper().strip()
                nu_p = st.text_input("Clave", type="password")
                if st.button("💾 Crear Usuario"):
                    if nu_n and nu_p:
                        config["usuarios"][nu_n] = nu_p
                        guardar_todo(inv, config, logs)
                        st.success("Usuario creado"); time.sleep(0.5); st.rerun()
                
                u_elim = st.selectbox("Borrar Usuario:", [u for u in config["usuarios"].keys() if u != "ADMIN"])
                if st.button("🗑️ Eliminar Usuario"):
                    del config["usuarios"][u_elim]
                    guardar_todo(inv, config, logs)
                    st.success("Usuario eliminado"); time.sleep(0.5); st.rerun()

            with st.expander("🏷️ 2. Marcas"):
                n_m = st.text_input("Nueva Marca").upper().strip()
                if st.button("➕ Añadir Marca"):
                    if n_m and n_m not in config["marcas"]:
                        config["marcas"].append(n_m)
                        guardar_todo(inv, config, logs)
                        st.success("Añadida"); time.sleep(0.5); st.rerun()
                
                m_b = st.selectbox("Borrar Marca:", config["marcas"])
                if st.button("🗑️ Borrar Seleccionada"):
                    config["marcas"].remove(m_b)
                    guardar_todo(inv, config, logs)
                    st.success("Eliminada"); time.sleep(0.5); st.rerun()

            with st.expander("🏘️ 3. Depósitos"):
                n_d = st.text_input("Nuevo Depósito").upper().strip()
                if st.button("➕ Crear Depo"):
                    if n_d:
                        config["depositos"].append(n_d)
                        guardar_todo(inv, config, logs)
                        st.success("Creado"); time.sleep(0.5); st.rerun()

            with st.expander("📜 4. Historial"):
                for l in logs:
                    st.write(f"**{l['fecha']}** | {l['usuario']}: {l['detalle']}")
