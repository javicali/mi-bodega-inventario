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
    nuevo_log = {
        "fecha": hora_correcta.strftime("%d/%m/%Y %H:%M"),
        "usuario": usuario,
        "accion": accion,
        "detalle": detalle
    }
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

# --- BUSCADOR CON BOTÓN ---
c_bus1, c_bus2 = st.columns([3, 1])
with c_bus1:
    busq = st.text_input("Escribe el Código:", key="in_busq").upper().strip()
with c_bus2:
    st.write("##") # Espaciador para alinear con el input
    ejecutar_busqueda = st.button("🔍 BUSCAR", use_container_width=True)

if ejecutar_busqueda and busq:
    res = [v for k, v in inv.items() if (k.split("_", 1)[1] if "_" in k else k) == busq]
    if res:
        for r in res:
            txt_caja = "caja" if r['stock'] == 1 else "cajas"
            st.info(f"📍 {r['deposito']} | **{r['marca']}**: {r['stock']} {txt_caja}")
    else:
        st.error(f"❌ El código '{busq}' no existe.")
elif ejecutar_busqueda and not busq:
    st.warning("⚠️ Por favor, escribe un código primero.")

st.divider()

if not st.session_state.mostrar_panel:
    if st.button("🚀 ENTRAR AL CONTROL", use_container_width=True, type="primary", key="btn_entrar"):
        st.session_state.mostrar_panel = True
        st.rerun()
else:
    if st.button("⬅️ VOLVER AL INICIO", use_container_width=True, key="btn_volver"):
        st.session_state.mostrar_panel = False
        st.rerun()

if st.session_state.mostrar_panel:
    dep_actual = st.selectbox("📍 Depósito Actual:", config["depositos"], key="sel_dep")
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
                    
                    txt_caja_panel = "caja" if info['stock'] == 1 else "cajas"
                    c2.markdown(f"📦 **{info['stock']}**\n<small>{txt_caja_panel}</small>", unsafe_allow_html=True)
                    
                    if st.session_state.edit_mode:
                        with c3:
                            cant = st.number_input("n", min_value=1, value=1, key=f"n_{key_id}", label_visibility="collapsed")
                            b1, b2, b3 = st.columns(3)
                            
                            if b1.button("➕", key=f"b1_{key_id}"): st.session_state[f"ask_add_{key_id}"] = True
                            if b2.button("➖", key=f"b2_{key_id}", disabled=(info['stock']==0)): st.session_state[f"ask_sub_{key_id}"] = True
                            if b3.button("🗑️", key=f"b3_{key_id}"): st.session_state[f"ask_del_{key_id}"] = True

                            if st.session_state.get(f"ask_add_{key_id}"):
                                if st.button(f"OK +{cant}?", key=f"conf_add_{key_id}", type="primary", use_container_width=True):
                                    inv[id_f]["stock"] += cant
                                    logs = registrar_log(logs, st.session_state.usuario_actual, "SUMA", f"+{cant} {cod_l}")
                                    guardar_todo(inv, config, logs); del st.session_state[f"ask_add_{key_id}"]; st.rerun()

                            if st.session_state.get(f"ask_sub_{key_id}"):
                                if st.button(f"OK -{cant}?", key=f"conf_sub_{key_id}", type="primary", use_container_width=True):
                                    inv[id_f]["stock"] -= cant
                                    logs = registrar_log(logs, st.session_state.usuario_actual, "RESTA", f"-{cant} {cod_l}")
                                    guardar_todo(inv, config, logs); del st.session_state[f"ask_sub_{key_id}"]; st.rerun()

                            if st.session_state.get(f"ask_del_{key_id}"):
                                if st.button("🚨 BORRAR", key=f"conf_del_{key_id}", type="primary", use_container_width=True):
                                    del inv[id_f]
                                    logs = registrar_log(logs, st.session_state.usuario_actual, "ELIMINAR", f"Borró {cod_l}")
                                    guardar_todo(inv, config, logs); del st.session_state[f"ask_del_{key_id}"]; st.rerun()

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔐 Acceso")
    if not st.session_state.edit_mode:
        u_sel = st.selectbox("Usuario", list(config["usuarios"].keys()), key="sb_u")
        p_sel = st.text_input("Clave", type="password", key="sb_p")
        if st.button("🔓 Entrar", key="login_btn"):
            if config["usuarios"].get(u_sel) == p_sel:
                st.session_state.edit_mode = True
                st.session_state.usuario_actual = u_sel
                st.rerun()
    else:
        st.success(f"👤 {st.session_state.usuario_actual}")
        if st.button("🔒 Salir", key="logout_btn"): st.session_state.edit_mode = False; st.rerun()
        
        st.divider()
        with st.expander("🆕 Registrar Nuevo Item"):
            rm = st.selectbox("Marca", config["marcas"], key="reg_m")
            rc = st.text_input("Código", key="reg_c").upper().strip()
            rd = st.selectbox("Depósito", config["depositos"], key="reg_d")
            if st.button("💾 Guardar Item", key="reg_btn"):
                if rc:
                    inv[f"{rd}_{rc}"] = {"marca": rm, "deposito": rd, "stock": 0}
                    logs = registrar_log(logs, st.session_state.usuario_actual, "CREACIÓN", f"Nuevo: {rc}")
                    guardar_todo(inv, config, logs); st.rerun()

        if st.session_state.usuario_actual == "ADMIN":
            st.warning("⚡ PANEL CONTROL ADMIN")
            
            with st.expander("👥 1. Usuarios"):
                un = st.text_input("Nombre Usuario", key="adm_un").upper()
                up = st.text_input("Contraseña", type="password", key="adm_up")
                if st.button("💾 Guardar Usuario", key="adm_ubtn"):
                    if un and up:
                        config["usuarios"][un] = up
                        guardar_todo(inv, config, logs); st.rerun()
                ub = st.selectbox("Eliminar Usuario:", [u for u in config["usuarios"].keys() if u != "ADMIN"], key="adm_sel_u")
                if st.button("🗑️ Eliminar Usuario", key="adm_ubdel"):
                    del config["usuarios"][ub]; guardar_todo(inv, config, logs); st.rerun()

            with st.expander("🏷️ 2. Marcas"):
                nm = st.text_input("Nueva Marca", key="adm_nm").upper()
                if st.button("➕ Añadir Marca", key="adm_mbtn"):
                    if nm and nm not in config["marcas"]:
                        config["marcas"].append(nm); guardar_todo(inv, config, logs); st.rerun()
                mb = st.selectbox("Eliminar Marca:", config["marcas"], key="adm_sel_m")
                if st.button("🗑️ Borrar Marca", key="adm_mbdel"):
                    config["marcas"].remove(mb); guardar_todo(inv, config, logs); st.rerun()

            with st.expander("🏘️ 3. Depósitos"):
                nd = st.text_input("Nuevo Depósito", key="adm_nd").upper()
                if st.button("➕ Crear Depósito", key="adm_dbtn"):
                    if nd and nd not in config["depositos"]:
                        config["depositos"].append(nd); guardar_todo(inv, config, logs); st.rerun()
                
                st.divider()
                st.write("**🚛 Trasladar Stock Completo**")
                dor = st.selectbox("Origen:", config["depositos"], key="tr_o")
                dde = st.selectbox("Destino:", config["depositos"], key="tr_d")
                if st.button("Mover Mercancía", key="tr_btn"):
                    if dor != dde:
                        items_m = [k for k, v in inv.items() if v["deposito"] == dor]
                        for k in items_m:
                            cp = k.split("_", 1)[1] if "_" in k else k
                            nid = f"{dde}_{cp}"
                            if nid in inv: inv[nid]["stock"] += inv[k]["stock"]
                            else:
                                inv[nid] = inv[k].copy()
                                inv[nid]["deposito"] = dde
                            del inv[k]
                        logs = registrar_log(logs, st.session_state.usuario_actual, "TRASLADO", f"De {dor} a {dde}")
                        guardar_todo(inv, config, logs); st.rerun()
                
                st.divider()
                del_d = st.selectbox("Borrar Depo Vacío:", config["depositos"], key="adm_del_d")
                if st.button("🗑️ Borrar Depósito", key="adm_d_delbtn"):
                    if any(v["deposito"] == del_d for v in inv.values()):
                        st.error("¡Tiene stock aún!")
                    elif len(config["depositos"]) > 1:
                        config["depositos"].remove(del_d); guardar_todo(inv, config, logs); st.rerun()

            with st.expander("📜 4. Historial"):
                for l in logs:
                    st.write(f"**{l['fecha']}** | 👤 {l.get('usuario','?')}: {l['detalle']}")
