import streamlit as st
import json
import os
import pandas as pd
import io
from datetime import datetime, timedelta

# --- CONFIGURACION DE ARCHIVOS ---
ARCHIVO_DB = "datos_bodega.json"
ARCHIVO_CONF = "config_bodega.json"
ARCHIVO_LOG = "historial_movimientos.json"

def cargar_json(archivo, defecto):
    if os.path.exists(archivo):
        with open(archivo, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return defecto
    return defecto

def guardar_todo(inv, conf, logs):
    with open(ARCHIVO_DB, "w", encoding="utf-8") as f:
        json.dump(inv, f, indent=4)
    with open(ARCHIVO_CONF, "w", encoding="utf-8") as f:
        json.dump(conf, f, indent=4)
    with open(ARCHIVO_LOG, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=4)

def registrar_log(logs, usuario, accion, detalle):
    hora = (datetime.now() - timedelta(hours=4)).strftime("%d/%m/%Y %H:%M")
    logs.insert(0, {"fecha": hora, "usuario": usuario, "accion": accion, "detalle": detalle})
    return logs[:200]

st.set_page_config(page_title="Bodega Inventario", layout="wide")

# --- ESTILOS CSS ---
st.markdown("""
<style>
    .block-container {padding-top: 1rem;}
    .stButton>button {width: 100%;}
    small { color: #888; }
    div.stButton > button:contains("CONFIRMAR SUMA") { background-color: #28a745 !important; color: white !important; }
    div.stButton > button:contains("CONFIRMAR RESTA") { background-color: #dc3545 !important; color: white !important; }
    div.stButton > button:contains("CONFIRMAR ELIMINACION") { background-color: #dc3545 !important; color: white !important; }
</style>
""", unsafe_allow_html=True)

inv = cargar_json(ARCHIVO_DB, {})
config = cargar_json(ARCHIVO_CONF, {"usuarios": {"ADMIN": "admin123"}, "depositos": ["SETAR"], "marcas": ["IRUN", "BOOTY"]})
logs = cargar_json(ARCHIVO_LOG, [])

if 'modo_panel' not in st.session_state: st.session_state.modo_panel = False
if 'edit_mode' not in st.session_state: st.session_state.edit_mode = False

# --- TARJETA DE EDICION ---
def mostrar_item_edicion(id_f, info, sufijo):
    cod_l = id_f.split("_", 1)[1] if "_" in id_f else id_f
    with st.container(border=True):
        c1, c2, c3 = st.columns([1.5, 1, 2.5])
        c1.markdown(f"**{cod_l}**\n<small>{info['marca']} | {info['deposito']}</small>", unsafe_allow_html=True)
        c2.markdown(f"**Stock: {info['stock']}**", unsafe_allow_html=True)
        
        with c3:
            key_msg = f"msg_{sufijo}_{id_f}"
            if key_msg in st.session_state:
                tipo, texto = st.session_state[key_msg]
                if tipo == "S": st.success(texto)
                elif tipo == "R": st.warning(texto)
                if st.button("OK", key=f"clr_{sufijo}_{id_f}"):
                    del st.session_state[key_msg]
                    st.rerun()
            else:
                cant = st.number_input("Cant", min_value=1, value=1, key=f"n_{sufijo}_{id_f}", label_visibility="collapsed")
                b1, b2, b3 = st.columns(3)
                if b1.button("+", key=f"add_{sufijo}_{id_f}"): st.session_state[f"conf_{sufijo}_{id_f}"] = "S"
                if b2.button("-", key=f"sub_{sufijo}_{id_f}", disabled=info['stock']==0): st.session_state[f"conf_{sufijo}_{id_f}"] = "R"
                if b3.button("x", key=f"del_{sufijo}_{id_f}"): st.session_state[f"conf_{sufijo}_{id_f}"] = "B"

                estado = st.session_state.get(f"conf_{sufijo}_{id_f}")
                if estado:
                    txt = f"CONFIRMAR {'SUMA' if estado=='S' else 'RESTA' if estado=='R' else 'ELIMINACION'}"
                    if st.button(txt, key=f"ok_{sufijo}_{id_f}", type="primary"):
                        usuario = st.session_state.get("usuario_actual", "ADMIN")
                        if estado == "S":
                            inv[id_f]["stock"] += cant
                            registrar_log(logs, usuario, "SUMA", f"+{cant} {cod_l}")
                            st.session_state[key_msg] = ("S", f"Sumadas {cant}")
                        elif estado == "R":
                            if inv[id_f]["stock"] >= cant:
                                inv[id_f]["stock"] -= cant
                                registrar_log(logs, usuario, "RESTA", f"-{cant} {cod_l}")
                                st.session_state[key_msg] = ("R", f"Restadas {cant}")
                        elif estado == "B":
                            registrar_log(logs, usuario, "BORRAR", f"Elimino {cod_l}")
                            del inv[id_f]
                        
                        guardar_todo(inv, config, logs)
                        if f"conf_{sufijo}_{id_f}" in st.session_state: del st.session_state[f"conf_{sufijo}_{id_f}"]
                        st.rerun()

# --- VISTA INICIO ---
if not st.session_state.modo_panel:
    st.title("Consulta de Inventario")
    c_izq, c_der = st.columns([4, 1])
    with c_izq:
        busq = st.text_input("Buscar codigo:", placeholder="Escriba codigo...").upper().strip()
    with c_der:
        st.write("##")
        btn_buscar = st.button("Buscar")

    if busq or btn_buscar:
        if busq:
            res = {k: v for k, v in inv.items() if (k.split("_", 1)[1] if "_" in k else k) == busq}
            if res:
                for k, v in res.items():
                    st.info(f"Codigo: **{busq}** | Marca: **{v['marca']}** | Deposito: **{v['deposito']}** | Cantidad: **{v['stock']}**")
            else:
                st.warning("No encontrado.")
# --- VISTA PANEL ---
else:
    st.title("Panel de Control")
    busq_edit = st.text_input("BUSCAR PARA EDITAR:").upper().strip()
    if busq_edit:
        res_e = {k: v for k, v in inv.items() if (k.split("_", 1)[1] if "_" in k else k) == busq_edit}
        for k, v in res_e.items(): mostrar_item_edicion(k, v, "edit_search")
    
    st.divider()
    dep_actual = st.selectbox("Deposito de trabajo:", config["depositos"])
    opciones_tabs = config["marcas"] + ["AGOTADOS"]
    tabs = st.tabs(opciones_tabs)
    
    for i, nombre_tab in enumerate(opciones_tabs):
        with tabs[i]:
            if nombre_tab == "AGOTADOS":
                items = {k: v for k, v in inv.items() if v['stock'] == 0 and v['deposito'] == dep_actual}
            else:
                items = {k: v for k, v in inv.items() if v['marca'] == nombre_tab and v['deposito'] == dep_actual and v['stock'] > 0}
            for k, v in sorted(items.items()):
                mostrar_item_edicion(k, v, f"tab_{i}")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("Acceso")
    if not st.session_state.edit_mode:
        u_log = st.selectbox("Usuario", list(config["usuarios"].keys()))
        p_log = st.text_input("Clave", type="password")
        if st.button("Entrar"):
            if config["usuarios"].get(u_log) == p_log:
                st.session_state.edit_mode, st.session_state.usuario_actual = True, u_log
                st.rerun()
    else:
        st.success(f"Usuario: {st.session_state.usuario_actual}")
        if st.button("VISTA INICIO" if st.session_state.modo_panel else "PANEL CONTROL"):
            st.session_state.modo_panel = not st.session_state.modo_panel
            st.rerun()
        if st.button("Salir"):
            st.session_state.edit_mode = False; st.session_state.modo_panel = False; st.rerun()

        st.divider()
        with st.expander("Crear Nuevo"):
            n_m = st.selectbox("Marca", config["marcas"])
            n_c = st.text_input("Codigo").upper().strip()
            n_d = st.selectbox("Deposito", config["depositos"])
            if st.button("Guardar"):
                if n_c:
                    inv[f"{n_d}_{n_c}"] = {"marca": n_m, "deposito": n_d, "stock": 0}
                    registrar_log(logs, st.session_state.usuario_actual, "CREACION", f"Nuevo: {n_c}")
                    guardar_todo(inv, config, logs); st.rerun()

        with st.expander("Traslados"):
            t_cod = st.text_input("Codigo a mover").upper().strip()
            t_de = st.selectbox("De", config["depositos"])
            t_a = st.selectbox("A", config["depositos"])
            t_cant = st.number_input("Cantidad", min_value=1, value=1)
            if st.button("Ejecutar Traslado"):
                id_origen = f"{t_de}_{t_cod}"
                if id_origen in inv and inv[id_origen]["stock"] >= t_cant:
                    inv[id_origen]["stock"] -= t_cant
                    id_destino = f"{t_a}_{t_cod}"
                    if id_destino not in inv:
                        inv[id_destino] = {"marca": inv[id_origen]["marca"], "deposito": t_a, "stock": 0}
                    inv[id_destino]["stock"] += t_cant
                    registrar_log(logs, st.session_state.usuario_actual, "TRASLADO", f"{t_cant} {t_cod} ({t_de}->{t_a})")
                    guardar_todo(inv, config, logs); st.rerun()

        with st.expander("Gestion Marcas"):
            nueva_m = st.text_input("Nueva Marca").upper().strip()
            if st.button("Anadir Marca"):
                if nueva_m and nueva_m not in config["marcas"]:
                    config["marcas"].append(nueva_m)
                    guardar_todo(inv, config, logs); st.rerun()

        st.divider()
        st.subheader("Reportes")
        if logs or inv:
            df_stk = pd.DataFrame([{"Deposito": v['deposito'], "Marca": v['marca'], "Codigo": k.split('_')[-1], "Cantidad": v['stock']} for k, v in inv.items()])
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_stk.to_excel(writer, index=False, sheet_name='Stock')
            st.download_button("DESCARGAR EXCEL", buffer.getvalue(), "Inventario.xlsx", use_container_width=True)

        with st.expander("Historial"):
            for l in logs[:10]:
                st.write(f"**{l['usuario']}**: {l['detalle']}")
                st.caption(l['fecha'])
                st.divider()
