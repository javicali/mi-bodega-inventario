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
            try: 
                return json.load(f)
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

# --- INICIO DE APP ---
st.set_page_config(page_title="Bodega Pro", layout="wide")

st.markdown("""<style>
    .block-container {padding-top: 1rem;}
    .stButton>button {padding: 0.2rem 0.5rem; width: 100%;}
</style>""", unsafe_allow_html=True)

inv = cargar_json(ARCHIVO_DB, {})
config = cargar_json(ARCHIVO_CONF, {"usuarios": {"ADMIN": "admin123"}, "depositos": ["SETAR"], "marcas": ["IRUN"]})
logs = cargar_json(ARCHIVO_LOG, [])

if 'edit_mode' not in st.session_state: st.session_state.edit_mode = False
if 'mostrar_panel' not in st.session_state: st.session_state.mostrar_panel = False
if 'usuario_actual' not in st.session_state: st.session_state.usuario_actual = ""

# --- FUNCIÓN PARA LIMPIAR INPUTS ---
def limpiar_y_recargar(id_f, sufijo):
    # Borramos el estado del número y de la confirmación para que vuelvan al inicio
    if f"n_{sufijo}_{id_f}" in st.session_state:
        st.session_state[f"n_{sufijo}_{id_f}"] = 1
    if f"conf_{sufijo}_{id_f}" in st.session_state:
        del st.session_state[f"conf_{sufijo}_{id_f}"]
    st.rerun()

# --- FUNCION UNICA DE TARJETA ---
def mostrar_item(id_f, info, sufijo):
    cod_l = id_f.split("_", 1)[1] if "_" in id_f else id_f
    with st.container(border=True):
        c1, c2, c3 = st.columns([1.5, 1, 2])
        c1.markdown(f"**{cod_l}**\n<small>{info['marca']} | {info['deposito']}</small>", unsafe_allow_html=True)
        txt_u = "caja" if info['stock'] == 1 else "cajas"
        c2.markdown(f"📦 **{info['stock']}**\n<small>{txt_u}</small>", unsafe_allow_html=True)
        
        if st.session_state.edit_mode:
            with c3:
                cant = st.number_input("n", min_value=1, value=1, key=f"n_{sufijo}_{id_f}", label_visibility="collapsed")
                col_btn = st.columns(3)
                if col_btn[0].button("➕", key=f"add_{sufijo}_{id_f}"): st.session_state[f"conf_{sufijo}_{id_f}"] = "S"
                if col_btn[1].button("➖", key=f"sub_{sufijo}_{id_f}", disabled=info['stock']==0): st.session_state[f"conf_{sufijo}_{id_f}"] = "R"
                if col_btn[2].button("🗑️", key=f"del_{sufijo}_{id_f}"): st.session_state[f"conf_{sufijo}_{id_f}"] = "B"

                estado = st.session_state.get(f"conf_{sufijo}_{id_f}")
                if estado == "S":
                    if st.button(f"OK +{cant}?", key=f"ok_s_{sufijo}_{id_f}", type="primary"):
                        inv[id_f]["stock"] += cant
                        registrar_log(logs, st.session_state.usuario_actual, "SUMA", f"+{cant} {cod_l}")
                        guardar_todo(inv, config, logs)
                        limpiar_y_recargar(id_f, sufijo)
                elif estado == "R":
                    if st.button(f"OK -{cant}?", key=f"ok_r_{sufijo}_{id_f}", type="primary"):
                        inv[id_f]["stock"] -= cant
                        registrar_log(logs, st.session_state.usuario_actual, "RESTA", f"-{cant} {cod_l}")
                        guardar_todo(inv, config, logs)
                        limpiar_y_recargar(id_f, sufijo)
                elif estado == "B":
                    if st.button("BORRAR?", key=f"ok_b_{sufijo}_{id_f}", type="primary"):
                        del inv[id_f]
                        registrar_log(logs, st.session_state.usuario_actual, "BORRAR", f"Eliminó {cod_l}")
                        guardar_todo(inv, config, logs)
                        limpiar_y_recargar(id_f, sufijo)
        else:
            c3.info("🔒 Loguéate")

# --- INTERFAZ ---
st.title("🏢 Inventario")

if not st.session_state.mostrar_panel:
    busq_p = st.text_input("🔍 Consultar Stock:", placeholder="Código...").upper().strip()
    if busq_p:
        encontrados = [v for k, v in inv.items() if (k.split("_", 1)[1] if "_" in k else k) == busq_p]
        for r in encontrados:
            st.info(f"📍 {r['deposito']} | **{r['marca']}**: {r['stock']} cajas")
    st.divider()
    if st.button("🚀 ENTRAR AL CONTROL", use_container_width=True, type="primary"):
        st.session_state.mostrar_panel = True
        st.rerun()
else:
    if st.button("⬅️ VOLVER AL INICIO", use_container_width=True):
        st.session_state.mostrar_panel = False
        st.rerun()
    
    st.subheader("🛠️ Gestión de Mercadería")
    busq_m = st.text_input("🔎 BUSCAR CÓDIGO PARA MODIFICAR:", placeholder="Escribe un código...").upper().strip()

    if busq_m:
        items_f = {k: v for k, v in inv.items() if (k.split("_", 1)[1] if "_" in k else k) == busq_m}
        if items_f:
            for id_f, info in items_f.items(): mostrar_item(id_f, info, "busq")
        else: st.error("Código no encontrado.")
    else:
        dep_sel = st.selectbox("📍 Depósito:", config["depositos"])
        tabs = st.tabs(config["marcas"] + ["⚠️ AGOTADOS"])
        for i, nombre_t in enumerate(config["marcas"] + ["⚠️ AGOTADOS"]):
            with tabs[i]:
                if nombre_t == "⚠️ AGOTADOS":
                    items = {k: v for k, v in inv.items() if v['stock'] == 0 and v['deposito'] == dep_sel}
                else:
                    items = {k: v for k, v in inv.items() if v['marca'] == nombre_t and v['deposito'] == dep_sel and v['stock'] > 0}
                for id_f, info in sorted(items.items()):
                    mostrar_item(id_f, info, "tab")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔐 Acceso")
    if not st.session_state.edit_mode:
        u = st.selectbox("Usuario", list(config["usuarios"].keys()))
        p = st.text_input("Clave", type="password")
        if st.button("🔓 Entrar"):
            if config.get("usuarios", {}).get(u) == p:
                st.session_state.edit_mode, st.session_state.usuario_actual = True, u
                st.rerun()
    else:
        st.success(f"👤 {st.session_state.usuario_actual}")
        if st.button("🔒 Salir"): st.session_state.edit_mode = False; st.rerun()
        st.divider()
        with st.expander("🆕 Registrar Nuevo"):
            rm = st.selectbox("Marca", config["marcas"])
            rc = st.text_input("Nuevo Código").upper().strip()
            rd = st.selectbox("Depósito", config["depositos"])
            if st.button("💾 Guardar"):
                if rc:
                    inv[f"{rd}_{rc}"] = {"marca": rm, "deposito": rd, "stock": 0}
                    guardar_todo(inv, config, logs); st.rerun()
        if st.session_state.usuario_actual == "ADMIN":
            with st.expander("📜 Historial"):
                for l in logs: st.write(f"**{l['fecha']}** | {l['usuario']}: {l['detalle']}")
