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

def registrar_log(logs, usuario, accion, detalle):
    hora = (datetime.now() - timedelta(hours=4)).strftime("%d/%m/%Y %H:%M")
    logs.insert(0, {"fecha": hora, "usuario": usuario, "accion": accion, "detalle": detalle})
    return logs[:200]

st.set_page_config(page_title="Bodega Pro", layout="wide")

st.markdown("""<style>
    .block-container {padding-top: 1rem;}
    .stButton>button {padding: 0.2rem 0.5rem; width: 100%;}
</style>""", unsafe_allow_html=True)

inv = cargar_json(ARCHIVO_DB, {})
config = cargar_json(ARCHIVO_CONF, {"usuarios": {"ADMIN": "admin123"}, "depositos": ["SETAR"], "marcas": ["IRUN", "BOOTY", "LEONESA", "YD", "ELT", "HHP", "TMILL"]})
logs = cargar_json(ARCHIVO_LOG, [])

if 'modo_panel' not in st.session_state: st.session_state.modo_panel = False
if 'edit_mode' not in st.session_state: st.session_state.edit_mode = False

# --- FUNCIÓN TARJETA EDICIÓN ---
def mostrar_item_edicion(id_f, info, sufijo):
    cod_l = id_f.split("_", 1)[1] if "_" in id_f else id_f
    with st.container(border=True):
        c1, c2, c3 = st.columns([1.5, 1, 2.2])
        c1.markdown(f"**{cod_l}**\n<small>{info['marca']} | {info['deposito']}</small>", unsafe_allow_html=True)
        txt_u = "caja" if info['stock'] == 1 else "cajas"
        c2.markdown(f"📦 **{info['stock']}**\n<small>{txt_u}</small>", unsafe_allow_html=True)
        
        with c3:
            cant = st.number_input("n", min_value=1, value=1, key=f"n_{sufijo}_{id_f}", label_visibility="collapsed")
            b1, b2, b3 = st.columns(3)
            if b1.button("➕", key=f"add_{sufijo}_{id_f}"): st.session_state[f"conf_{sufijo}_{id_f}"] = "S"
            if b2.button("➖", key=f"sub_{sufijo}_{id_f}", disabled=info['stock']==0): st.session_state[f"conf_{sufijo}_{id_f}"] = "R"
            if b3.button("🗑️", key=f"del_{sufijo}_{id_f}"): st.session_state[f"conf_{sufijo}_{id_f}"] = "B"

            estado = st.session_state.get(f"conf_{sufijo}_{id_f}")
            if estado:
                if st.button("CONFIRMAR OK", key=f"ok_{sufijo}_{id_f}", type="primary"):
                    if estado == "S": 
                        inv[id_f]["stock"] += cant
                        registrar_log(logs, st.session_state.usuario_actual, "SUMA", f"+{cant} {cod_l}")
                    elif estado == "R": 
                        inv[id_f]["stock"] -= cant
                        registrar_log(logs, st.session_state.usuario_actual, "RESTA", f"-{cant} {cod_l}")
                    elif estado == "B": 
                        registrar_log(logs, st.session_state.usuario_actual, "BORRAR", f"Eliminó {cod_l}")
                        del inv[id_f]
                    guardar_todo(inv, config, logs)
                    del st.session_state[f"conf_{sufijo}_{id_f}"]
                    st.rerun()

# --- INTERFAZ PRINCIPAL ---
if not st.session_state.modo_panel:
    st.title("🏢 Consulta de Inventario")
    busq = st.text_input("🔍 Buscar código:", key="main_search").upper().strip()
    if busq:
        res = {k: v for k, v in inv.items() if (k.split("_", 1)[1] if "_" in k else k) == busq}
        for k, v in res.items():
            st.success(f"✅ **{busq}** ({v['marca']}) en **{v['deposito']}**: {v['stock']} cajas")
    
    st.divider()
    if st.checkbox("👁️ Ver Stock General"):
        dep_v = st.selectbox("Depósito:", config["depositos"], key="view_dep")
        tabs = st.tabs(config["marcas"])
        for i, m in enumerate(config["marcas"]):
            with tabs[i]:
                items = {k: v for k, v in inv.items() if v.get('marca')==m and v.get('deposito')==dep_v and v.get('stock',0)>0}
                for kid, info in items.items():
                    st.write(f"**{kid.split('_')[-1]}**: {info['stock']} cajas")

else:
    st.title("🛠️ Panel de Modificación")
    busq_m = st.text_input("🔎 Buscar para editar:", key="edit_search").upper().strip()
    if busq_m:
        items_f = {k: v for k, v in inv.items() if (k.split("_", 1)[1] if "_" in k else k) == busq_m}
        for id_f, info in items_f.items(): mostrar_item_edicion(id_f, info, "busq")
    else:
        dep_sel = st.selectbox("📍 Depósito:", config["depositos"], key="edit_dep")
        tabs_e = st.tabs(config["marcas"] + ["⚠️ AGOTADOS"])
        for i, m_e in enumerate(config["marcas"] + ["⚠️ AGOTADOS"]):
            with tabs_e[i]:
                if m_e == "⚠️ AGOTADOS":
                    items = {k: v for k, v in inv.items() if v.get('stock',0)==0 and v.get('deposito')==dep_sel}
                else:
                    items = {k: v for k, v in inv.items() if v.get('marca')==m_e and v.get('deposito')==dep_sel and v.get('stock',0)>0}
                for id_f, info in sorted(items.items()): mostrar_item_edicion(id_f, info, "tab")

# --- SIDEBAR (CONFIGURACIÓN Y ACCESO) ---
with st.sidebar:
    st.header("🔐 Acceso")
    if not st.session_state.edit_mode:
        u = st.selectbox("Usuario", list(config["usuarios"].keys()))
        p = st.text_input("Clave", type="password")
        if st.button("🔓 Entrar"):
            if config["usuarios"].get(u) == p:
                st.session_state.edit_mode, st.session_state.usuario_actual = True, u
                st.rerun()
    else:
        st.success(f"👤 {st.session_state.usuario_actual}")
        if st.button("🏠" if st.session_state.modo_panel else "⚙️ PANEL CONTROL"):
            st.session_state.modo_panel = not st.session_state.modo_panel
            st.rerun()
        
        if st.button("🔒 Salir"):
            st.session_state.edit_mode = False
            st.session_state.modo_panel = False
            st.rerun()

        st.divider()
        # --- OPCIONES DE ADMIN ---
        if st.session_state.usuario_actual == "ADMIN":
            with st.expander("📝 Historial de Movimientos"):
                for l in logs: st.write(f"<small>{l['fecha']} | {l['usuario']} | {l['detalle']}</small>", unsafe_allow_html=True)
            
            with st.expander("🏘️ Gestionar Depósitos"):
                nuevo_d = st.text_input("Nombre Depósito").upper()
                if st.button("➕ Añadir Depo"):
                    if nuevo_d and nuevo_d not in config["depositos"]:
                        config["depositos"].append(nuevo_d)
                        guardar_todo(inv, config, logs); st.rerun()
            
            with st.expander("🏷️ Gestionar Marcas"):
                nueva_m = st.text_input("Nombre Marca").upper()
                if st.button("➕ Añadir Marca"):
                    if nueva_m and nueva_m not in config["marcas"]:
                        config["marcas"].append(nueva_m)
                        guardar_todo(inv, config, logs); st.rerun()
            
            with st.expander("👥 Gestionar Usuarios"):
                nu = st.text_input("Nuevo Usuario").upper()
                np = st.text_input("Clave Usuario", type="password")
                if st.button("💾 Crear Usuario"):
                    config["usuarios"][nu] = np
                    guardar_todo(inv, config, logs); st.rerun()

        with st.expander("🆕 Registrar Nuevo Código"):
            rm = st.selectbox("Marca", config["marcas"], key="reg_m")
            rc = st.text_input("Código", key="reg_c").upper().strip()
            rd = st.selectbox("Depósito", config["depositos"], key="reg_d")
            if st.button("💾 Guardar Nuevo"):
                if rc:
                    inv[f"{rd}_{rc}"] = {"marca": rm, "deposito": rd, "stock": 0}
                    registrar_log(logs, st.session_state.usuario_actual, "CREACION", f"Creó {rc}")
                    guardar_todo(inv, config, logs); st.rerun()
