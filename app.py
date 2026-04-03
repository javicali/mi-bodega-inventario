import streamlit as st
import json
import os
import pandas as pd
import io
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

st.set_page_config(page_title="Bodega Pro Ultra", layout="wide")

# --- ESTILOS CSS PERSONALIZADOS ---
st.markdown("""
<style>
    .block-container {padding-top: 1rem;}
    .stButton>button {width: 100%;}
    small { color: #888; }
    
    div.stButton > button:contains("CONFIRMAR SUMA") {
        background-color: #28a745 !important;
        color: white !important;
    }
    div.stButton > button:contains("CONFIRMAR RESTA") {
        background-color: #dc3545 !important;
        color: white !important;
    }
    div.stButton > button:contains("ELIMINAR") {
        background-color: #6c757d !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

# Cargar datos
inv = cargar_json(ARCHIVO_DB, {})
config = cargar_json(ARCHIVO_CONF, {"usuarios": {"ADMIN": "admin123"}, "depositos": ["SETAR"], "marcas": ["IRUN", "BOOTY"]})
logs = cargar_json(ARCHIVO_LOG, [])

if 'modo_panel' not in st.session_state: st.session_state.modo_panel = False
if 'edit_mode' not in st.session_state: st.session_state.edit_mode = False

# --- FUNCIÓN TARJETA DE EDICIÓN ---
def mostrar_item_edicion(id_f, info, sufijo):
    cod_l = id_f.split("_", 1)[1] if "_" in id_f else id_f
    with st.container(border=True):
        c1, c2, c3 = st.columns([1.5, 1, 2.2])
        c1.markdown(f"**{cod_l}**\n<small>{info['marca']} | {info['deposito']}</small>", unsafe_allow_html=True)
        c2.markdown(f"📦 **{info['stock']}**\n<small>unidades</small>", unsafe_allow_html=True)
        
        with c3:
            key_msg = f"msg_{sufijo}_{id_f}"
            if key_msg in st.session_state:
                tipo, texto = st.session_state[key_msg]
                if tipo == "S": st.success(texto)
                elif tipo == "R": st.warning(texto)
                elif tipo == "B": st.error(texto)
                if st.button("OK ✅", key=f"clr_{sufijo}_{id_f}"):
                    del st.session_state[key_msg]
                    st.rerun()
            else:
                cant = st.number_input("Cantidad", min_value=1, value=1, key=f"n_{sufijo}_{id_f}", label_visibility="collapsed")
                b1, b2, b3 = st.columns(3)
                if b1.button("➕", key=f"add_{sufijo}_{id_f}"): st.session_state[f"conf_{sufijo}_{id_f}"] = "S"
                if b2.button("➖", key=f"sub_{sufijo}_{id_f}", disabled=info['stock']==0): st.session_state[f"conf_{sufijo}_{id_f}"] = "R"
                if b3.button("🗑️", key=f"del_{sufijo}_{id_f}"): st.session_state[f"conf_{sufijo}_{id_f}"] = "B"

                estado = st.session_state.get(f"conf_{sufijo}_{id_f}")
                if estado:
                    txt_btn = f"CONFIRMAR {'SUMA' if estado=='S' else 'RESTA' if estado=='R' else 'ELIMINACIÓN'}"
                    if st.button(txt_btn, key=f"ok_{sufijo}_{id_f}", type="primary"):
                        usuario = st.session_state.usuario_actual
                        if estado == "S":
                            inv[id_f]["stock"] += cant
                            registrar_log(logs, usuario, "SUMA", f"+{cant} {cod_l}")
                            st.session_state[key_msg] = ("S", f"Añadidas {cant} unidades")
                        elif estado == "R":
                            inv[id_f]["stock"] -= cant
                            registrar_log(logs, usuario, "RESTA", f"-{cant} {cod_l}")
                            st.session_state[key_msg] = ("R", f"Restadas {cant} unidades")
                        elif estado == "B":
                            registrar_log(logs, usuario, "BORRAR", f"Eliminó {cod_l}")
                            st.session_state[key_msg] = ("B", "Código eliminado")
                            del inv[id_f]
                        
                        guardar_todo(inv, config, logs)
                        del st.session_state[f"conf_{sufijo}_{id_f}"]
                        st.rerun()

# --- LÓGICA PRINCIPAL ---
if not st.session_state.modo_panel:
    st.title("🏢 Consulta de Inventario")
    busq = st.text_input("Buscar código:", placeholder="Ingrese código...").upper().strip()
    if busq:
        res = {k: v for k, v in inv.items() if (k.split("_", 1)[1] if "_" in k else k) == busq}
        if res:
            for k, v in res.items():
                st.info(f"**{busq}** ({v['marca']}) en **{v['deposito']}**: {v['stock']} unidades")
        else: st.warning("No encontrado.")
    
    st.divider()
    if st.checkbox("👁️ Ver Stock General"):
        d_v = st.selectbox("Depósito:", config["depositos"])
        tbs = st.tabs(config["marcas"])
        for i, m in enumerate(config["marcas"]):
            with tbs[i]:
                it = {k: v for k, v in inv.items() if v['marca']==m and v['deposito']==d_v and v['stock']>0}
                for kid, info in it.items(): st.write(f"**{kid.split('_')[-1]}**: {info['stock']}")

else:
    st.title("🛠️ Panel de Control")
    b_p = st.text_input("🔎 BUSCAR PARA EDITAR:").upper().strip()
    if b_p:
        res_p = {k: v for k, v in inv.items() if (k.split("_", 1)[1] if "_" in k else k) == b_p}
        for k, v in res_p.items(): mostrar_item_edicion(k, v, "p_busq")
    
    st.divider()
    dep_p = st.selectbox("📍 Depósito de trabajo:", config["depositos"])
    tabs_p = st.tabs(config["marcas"] + ["⚠️ AGOTADOS"])
    for i, m_p in enumerate(config["marcas"] + ["⚠️ AGOTADOS"]):
        with tabs_p[i]:
            if m_p == "⚠️ AGOTADOS": it_p = {k: v for k, v in inv.items() if v['stock']==0 and v['deposito']==dep_p}
            else: it_p = {k: v for k, v in inv.items() if v['marca']==m_p and v['deposito']==dep_p and v['stock']>0}
            for k, v in sorted(it_p.items()): mostrar_item_edicion(k, v, f"p_tab_{i}")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔐 Acceso")
    if not st.session_state.edit_mode:
        u_log = st.selectbox("Usuario", list(config["usuarios"].keys()))
        p_log = st.text_input("Clave", type="password")
        if st.button("🔓 Entrar"):
            if config["usuarios"].get(u_log) == p_log:
                st.session_state.edit_mode, st.session_state.usuario_actual = True, u_log
                st.rerun()
    else:
        st.success(f"👤 {st.session_state.usuario_actual}")
        if st.button("🏠 VISTA INICIO" if st.session_state.modo_panel else "⚙️ PANEL CONTROL"):
            st.session_state.modo_panel = not st.session_state.modo_panel
            st.rerun()
        if st.button("🔒 Salir"):
            st.session_state.edit_mode = False; st.rerun()

        st.divider()
        with st.expander("🆕 Nuevo Código"):
            n_m = st.selectbox("Marca", config["marcas"])
            n_c = st.text_input("Código").upper().strip()
            n_d = st.selectbox("Depósito", config["depositos"])
            if st.button("💾 Crear"):
                inv[f"{n_d}_{n_c}"] = {"marca": n_m, "deposito": n_d, "stock": 0}
                registrar_log(logs, st.session_state.usuario_actual, "CREACION", f"Nuevo: {n_c}")
                guardar_todo(inv, config, logs); st.rerun()

        with st.expander("🔄 Traslados"):
            tc = st.text_input("Cód a trasladar").upper().strip()
            to = st.selectbox("De", config["depositos"], key="t_de")
            td = st.selectbox("A", config["depositos"], key="t_a")
            tq = st.number_input("Cant.", min_value=1, value=1)
            if st.button("Ejecutar Traslado"):
                if f"{to}_{tc}" in inv and inv[f"{to}_{tc}"]["stock"] >= tq:
                    inv[f"{to}_{tc}"]["stock"] -= tq
                    if f"{td}_{tc}" not in inv: inv[f"{td}_{tc}"] = {"marca": inv[f"{to}_{tc}"]["marca"], "deposito": td, "stock": 0}
                    inv[f"{td}_{tc}"]["stock"] += tq
                    registrar_log(logs, st.session_state.usuario_actual, "TRASLADO", f"{tq} {tc} ({to}->{td})")
                    guardar_todo(inv, config, logs); st.rerun()

        # --- SECCIÓN DE HISTORIAL Y REPORTES ---
        st.divider()
        st.subheader("📝 Reportes e Historial")
        
        if logs or inv:
            df_mov = pd.DataFrame(logs).reindex(columns=['fecha', 'usuario', 'accion', 'detalle'])
            df_stk = pd.DataFrame([{"Depo": v['deposito'], "Marca": v['marca'], "Código": k.split('_')[-1], "Cant": v['stock']} for k, v in inv.items()])
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_stk.to_excel(writer, index=False, sheet_name='STOCK')
                df_mov.to_excel(writer, index=False, sheet_name='LOGS')
            
            st.download_button("📥 DESCARGAR EXCEL", buffer.getvalue(), f"Reporte_{datetime.now().strftime('%d_%m')}.xlsx", use_container_width=True)

        with st.expander("👁️ Ver últimos movimientos"):
            for l in logs[:15]:
                st.markdown(f"**👤 {l.get('usuario','???')}**: {l['detalle']}<br><small>{l['fecha']}</small>", unsafe_allow_html=True)
                st.divider()
            if st.button("🗑️ Limpiar Historial"):
                logs = []; guardar_todo(inv, config, logs); st.rerun()
