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
    .stAlert {padding: 0.5rem;}
</style>""", unsafe_allow_html=True)

inv = cargar_json(ARCHIVO_DB, {})
config = cargar_json(ARCHIVO_CONF, {"usuarios": {"ADMIN": "admin123"}, "depositos": ["SETAR"], "marcas": ["IRUN"]})
logs = cargar_json(ARCHIVO_LOG, [])

if 'mostrar_panel' not in st.session_state: st.session_state.mostrar_panel = False
if 'edit_mode' not in st.session_state: st.session_state.edit_mode = False

# --- FUNCIÓN TARJETA ---
def mostrar_item(id_f, info, sufijo, modo_edicion=False):
    cod_l = id_f.split("_", 1)[1] if "_" in id_f else id_f
    with st.container(border=True):
        c1, c2, c3 = st.columns([1.5, 1, 2])
        c1.markdown(f"**{cod_l}**\n<small>{info['marca']} | {info['deposito']}</small>", unsafe_allow_html=True)
        txt_u = "caja" if info['stock'] == 1 else "cajas"
        c2.markdown(f"📦 **{info['stock']}**\n<small>{txt_u}</small>", unsafe_allow_html=True)
        
        if modo_edicion and st.session_state.edit_mode:
            with c3:
                cant = st.number_input("n", min_value=1, value=1, key=f"n_{sufijo}_{id_f}", label_visibility="collapsed")
                col_btn = st.columns(3)
                if col_btn[0].button("➕", key=f"add_{sufijo}_{id_f}"): st.session_state[f"conf_{sufijo}_{id_f}"] = "S"
                if col_btn[1].button("➖", key=f"sub_{sufijo}_{id_f}", disabled=info['stock']==0): st.session_state[f"conf_{sufijo}_{id_f}"] = "R"
                if col_btn[2].button("🗑️", key=f"del_{sufijo}_{id_f}"): st.session_state[f"conf_{sufijo}_{id_f}"] = "B"

                estado = st.session_state.get(f"conf_{sufijo}_{id_f}")
                if estado:
                    if st.button("CONFIRMAR OK", key=f"ok_{sufijo}_{id_f}", type="primary"):
                        if estado == "S": inv[id_f]["stock"] += cant
                        elif estado == "R": inv[id_f]["stock"] -= cant
                        elif estado == "B": del inv[id_f]
                        guardar_todo(inv, config, logs)
                        if f"n_{sufijo}_{id_f}" in st.session_state: st.session_state[f"n_{sufijo}_{id_f}"] = 1
                        del st.session_state[f"conf_{sufijo}_{id_f}"]
                        st.rerun()

# --- LÓGICA DE PÁGINAS ---

if not st.session_state.mostrar_panel:
    # ================= PÁGINA DE CONSULTA (PÚBLICA) =================
    st.title("🔍 Consulta de Stock")
    
    # 1. BUSCADOR POR CÓDIGO
    c_p1, c_p2 = st.columns([4, 1])
    with c_p1:
        busq_p = st.text_input("Buscar código específico:", placeholder="Escriba aquí...").upper().strip()
    with c_p2:
        st.write("##")
        btn_lupa = st.button("🔍 Buscar")

    if busq_p:
        encontrados = {k: v for k, v in inv.items() if (k.split("_", 1)[1] if "_" in k else k) == busq_p}
        if encontrados:
            for id_f, info in encontrados.items():
                txt_c = "caja" if info['stock'] == 1 else "cajas"
                st.success(f"✅ **{busq_p}** | {info['marca']} | Depósito: **{info['deposito']}** | Stock: **{info['stock']} {txt_c}**")
        else:
            st.error("❌ Código no encontrado.")
    
    st.divider()
    
    # 2. VER TODO EL INVENTARIO (LECTURA)
    st.subheader("📦 Vista General por Depósito")
    dep_v = st.selectbox("Seleccione Depósito para ver todo:", config["depositos"])
    tab_m = st.tabs(config["marcas"])
    for i, m_nombre in enumerate(config["marcas"]):
        with tab_m[i]:
            items_v = {k: v for k, v in inv.items() if v['marca'] == m_nombre and v['deposito'] == dep_v and v['stock'] > 0}
            if items_v:
                for id_f, info in sorted(items_v.items()):
                    mostrar_item(id_f, info, "view", modo_edicion=False)
            else:
                st.write("No hay stock en esta marca.")

    # 3. BOTÓN DISCRETO AL FINAL
    st.write("---")
    if st.button("⚙️ Configuración / Entrada al Controlador", use_container_width=True):
        st.session_state.mostrar_panel = True
        st.rerun()

else:
    # ================= PÁGINA DE CONTROL (MODIFICACIÓN) =================
    st.title("🛠️ Panel de Control")
    if st.button("⬅️ VOLVER A CONSULTAS", use_container_width=True):
        st.session_state.mostrar_panel = False
        st.rerun()
    
    st.divider()
    busq_m = st.text_input("🔎 BUSCAR PARA EDITAR:", placeholder="Escriba código...").upper().strip()

    if busq_m:
        items_f = {k: v for k, v in inv.items() if (k.split("_", 1)[1] if "_" in k else k) == busq_m}
        if items_f:
            for id_f, info in items_f.items(): mostrar_item(id_f, info, "ed_busq", modo_edicion=True)
        else: st.error("No existe.")
    else:
        dep_sel = st.selectbox("📍 Editar en Depósito:", config["depositos"])
        tabs_e = st.tabs(config["marcas"] + ["⚠️ AGOTADOS"])
        for i, nombre_t in enumerate(config["marcas"] + ["⚠️ AGOTADOS"]):
            with tabs_e[i]:
                if nombre_t == "⚠️ AGOTADOS":
                    items = {k: v for k, v in inv.items() if v['stock'] == 0 and v['deposito'] == dep_sel}
                else:
                    items = {k: v for k, v in inv.items() if v['marca'] == nombre_t and v['deposito'] == dep_sel and v['stock'] > 0}
                for id_f, info in sorted(items.items()):
                    mostrar_item(id_f, info, "ed_tab", modo_edicion=True)

# --- SIDEBAR (ACCESO) ---
with st.sidebar:
    st.header("🔐 Acceso")
    if not st.session_state.edit_mode:
        u = st.selectbox("Usuario", list(config["usuarios"].keys()))
        p = st.text_input("Clave", type="password")
        if st.button("🔓 Desbloquear Edición"):
            if config.get("usuarios", {}).get(u) == p:
                st.session_state.edit_mode, st.session_state.usuario_actual = True, u
                st.rerun()
    else:
        st.success(f"👤 {st.session_state.usuario_actual}")
        if st.button("🔒 Bloquear"): st.session_state.edit_mode = False; st.rerun()
        st.divider()
        with st.expander("🆕 Registrar Nuevo"):
            rm = st.selectbox("Marca", config["marcas"])
            rc = st.text_input("Nuevo Código").upper().strip()
            rd = st.selectbox("Depósito", config["depositos"])
            if st.button("💾 Guardar"):
                if rc:
                    inv[f"{rd}_{rc}"] = {"marca": rm, "deposito": rd, "stock": 0}
                    guardar_todo(inv, config, logs); st.rerun()
