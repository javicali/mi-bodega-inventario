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
    
    /* Colores para botones de confirmación */
    div.stButton > button:contains("CONFIRMAR SUMA") {
        background-color: #28a745 !important;
        color: white !important;
        border: none;
    }
    div.stButton > button:contains("CONFIRMAR RESTA") {
        background-color: #dc3545 !important;
        color: white !important;
        border: none;
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

# --- FUNCIÓN TARJETA DE EDICIÓN (CON MENSAJES PERSISTENTES) ---
def mostrar_item_edicion(id_f, info, sufijo):
    cod_l = id_f.split("_", 1)[1] if "_" in id_f else id_f
    with st.container(border=True):
        c1, c2, c3 = st.columns([1.5, 1, 2.2])
        c1.markdown(f"**{cod_l}**\n<small>{info['marca']} | {info['deposito']}</small>", unsafe_allow_html=True)
        c2.markdown(f"📦 **{info['stock']}**\n<small>unidades</small>", unsafe_allow_html=True)
        
        with c3:
            cant = st.number_input("Cantidad", min_value=1, value=1, key=f"n_{sufijo}_{id_f}", label_visibility="collapsed")
            b1, b2, b3 = st.columns(3)
            if b1.button("➕", key=f"add_{sufijo}_{id_f}"): st.session_state[f"conf_{sufijo}_{id_f}"] = "S"
            if b2.button("➖", key=f"sub_{sufijo}_{id_f}", disabled=info['stock']==0): st.session_state[f"conf_{sufijo}_{id_f}"] = "R"
            if b3.button("🗑️", key=f"del_{sufijo}_{id_f}"): st.session_state[f"conf_{sufijo}_{id_f}"] = "B"

            estado = st.session_state.get(f"conf_{sufijo}_{id_f}")
            
            # Si ya se hizo clic en confirmar y los datos se guardaron, mostramos el mensaje de éxito
            if f"msg_{sufijo}_{id_f}" in st.session_state:
                tipo, texto = st.session_state[f"msg_{sufijo}_{id_f}"]
                if tipo == "S": st.success(texto)
                elif tipo == "R": st.warning(texto)
                elif tipo == "B": st.error(texto)
                if st.button("OK, cerrar aviso", key=f"clr_{sufijo}_{id_f}"):
                    del st.session_state[f"msg_{sufijo}_{id_f}"]
                    st.rerun()

            # Lógica de los botones de confirmación
            elif estado:
                txt_btn = "CONFIRMAR"
                if estado == "S": txt_btn = f"CONFIRMAR SUMA (+{cant})"
                elif estado == "R": txt_btn = f"CONFIRMAR RESTA (-{cant})"
                elif estado == "B": txt_btn = "CONFIRMAR ELIMINACIÓN"

                if st.button(txt_btn, key=f"ok_{sufijo}_{id_f}", type="primary"):
                    if estado == "S": 
                        inv[id_f]["stock"] += cant
                        registrar_log(logs, st.session_state.usuario_actual, "SUMA", f"+{cant} {cod_l}")
                        st.session_state[f"msg_{sufijo}_{id_f}"] = ("S", f"Añadidas {cant} cajas")
                    elif estado == "R": 
                        inv[id_f]["stock"] -= cant
                        registrar_log(logs, st.session_state.usuario_actual, "RESTA", f"-{cant} {cod_l}")
                        st.session_state[f"msg_{sufijo}_{id_f}"] = ("R", f"Salieron {cant} cajas")
                    elif estado == "B": 
                        registrar_log(logs, st.session_state.usuario_actual, "BORRAR", f"Eliminó {cod_l}")
                        st.session_state[f"msg_{sufijo}_{id_f}"] = ("B", f"Código eliminado")
                        del inv[id_f]
                    
                    guardar_todo(inv, config, logs)
                    del st.session_state[f"conf_{sufijo}_{id_f}"]
                    st.rerun()
# --- LÓGICA DE INTERFAZ PRINCIPAL ---
if not st.session_state.modo_panel:
    st.title("🏢 Consulta de Inventario")
    col_busq, col_btn = st.columns([4, 1])
    with col_busq:
        busq = st.text_input("Buscar código:", key="main_search", placeholder="Ingrese código...").upper().strip()
    with col_btn:
        st.write("##")
        ejecutar_busq = st.button("🔍 Buscar", use_container_width=True)

    if busq or ejecutar_busq:
        res = {k: v for k, v in inv.items() if (k.split("_", 1)[1] if "_" in k else k) == busq}
        if res:
            for k, v in res.items():
                msg = f"**{busq}** ({v['marca']}) en **{v['deposito']}**: {v['stock']} cajas"
                if v['stock'] > 0: st.success(f"✅ {msg}")
                else: st.error(f"🚨 AGOTADO: {msg}")
        elif busq:
            st.warning("⚠️ Código no encontrado.")
    
    st.divider()
    if st.checkbox("👁️ Ver Stock General por Depósito"):
        d_v = st.selectbox("Seleccione Depósito:", config["depositos"])
        tbs = st.tabs(config["marcas"])
        for i, m in enumerate(config["marcas"]):
            with tbs[i]:
                it = {k: v for k, v in inv.items() if v.get('marca')==m and v.get('deposito')==d_v and v.get('stock',0)>0}
                if not it: st.write("_Sin existencias._")
                for kid, info in it.items(): st.write(f"**{kid.split('_')[-1]}**: {info['stock']} unidades")

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
            if m_p == "⚠️ AGOTADOS": it_p = {k: v for k, v in inv.items() if v.get('stock',0)==0 and v.get('deposito')==dep_p}
            else: it_p = {k: v for k, v in inv.items() if v.get('marca')==m_p and v.get('deposito')==dep_p and v.get('stock',0)>0}
            if it_p:
                for k, v in sorted(it_p.items()): mostrar_item_edicion(k, v, f"p_tab_{i}")
            else: st.write(f"Vacio.")

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
            st.session_state.edit_mode = False; st.session_state.modo_panel = False; st.rerun()

        st.divider()
        with st.expander("🆕 Nuevo Código"):
            n_m, n_c, n_d = st.selectbox("Marca", config["marcas"]), st.text_input("Código").upper().strip(), st.selectbox("Depósito", config["depositos"])
            if st.button("💾 Crear"):
                if n_c:
                    inv[f"{n_d}_{n_c}"] = {"marca": n_m, "deposito": n_d, "stock": 0}
                    registrar_log(logs, st.session_state.usuario_actual, "CREACION", f"Nuevo: {n_c}")
                    guardar_todo(inv, config, logs); st.toast(f"Código {n_c} creado"); st.rerun()

        if st.session_state.usuario_actual == "ADMIN":
            with st.expander("👥 Usuarios"):
                for us in list(config["usuarios"].keys()):
                    c1, c2 = st.columns([3, 1])
                    c1.write(us)
                    if us != "ADMIN" and c2.button("🗑️", key=f"du_{us}"):
                        del config["usuarios"][us]; guardar_todo(inv, config, logs); st.rerun()
                nu, np = st.text_input("Nombre"), st.text_input("Pass", type="password")
                if st.button("➕ Crear Usuario"):
                    if nu: config["usuarios"][nu.upper()] = np; guardar_todo(inv, config, logs); st.rerun()

            with st.expander("🏷️ Marcas"):
                for m_l in config["marcas"]:
                    c1, c2 = st.columns([3, 1])
                    c1.write(m_l)
                    if c2.button("🗑️", key=f"dm_{m_l}"):
                        config["marcas"].remove(m_l); guardar_todo(inv, config, logs); st.rerun()
                nm = st.text_input("Nueva Marca").upper().strip()
                if st.button("➕ Añadir Marca"):
                    if nm and nm not in config["marcas"]: config["marcas"].append(nm); guardar_todo(inv, config, logs); st.rerun()

            with st.expander("🏘️ Depósitos"):
                for d_l in config["depositos"]:
                    c1, c2, c3 = st.columns([2, 0.5, 0.5])
                    c1.write(f"📍 {d_l}")
                    if c2.button("✏️", key=f"ed_{d_l}"): st.session_state[f"editing_{d_l}"] = True
                    if c3.button("🗑️", key=f"dd_{d_l}"): config["depositos"].remove(d_l); guardar_todo(inv, config, logs); st.rerun()
                    if st.session_state.get(f"editing_{d_l}"):
                        nuevo_nombre = st.text_input("Nuevo nombre:", value=d_l, key=f"nn_{d_l}").upper().strip()
                        if st.button("✅ Ok", key=f"okd_{d_l}"):
                            config["depositos"][config["depositos"].index(d_l)] = nuevo_nombre
                            ni = { (f"{nuevo_nombre}_{k.split('_',1)[1]}" if v["deposito"]==d_l else k): (v if v["deposito"]!=d_l else {**v, "deposito": nuevo_nombre}) for k,v in inv.items()}
                            inv.clear(); inv.update(ni); guardar_todo(inv, config, logs); st.rerun()

            with st.expander("🔄 Traslados"):
                tc, to, td = st.text_input("Cód").upper().strip(), st.selectbox("De", config["depositos"]), st.selectbox("A", config["depositos"])
                tq = st.number_input("C", min_value=1, value=1)
                if st.button("Trasladar"):
                    if f"{to}_{tc}" in inv and inv[f"{to}_{tc}"]["stock"] >= tq:
                        inv[f"{to}_{tc}"]["stock"] -= tq
                        id_f = f"{td}_{tc}"
                        if id_f not in inv: inv[id_f] = {"marca": inv[f"{to}_{tc}"]["marca"], "deposito": td, "stock": 0}
                        inv[id_f]["stock"] += tq
                        registrar_log(logs, st.session_state.usuario_actual, "TRASLADO", f"{tq} {tc} ({to}->{td})")
                        guardar_todo(inv, config, logs); st.toast("Traslado exitoso"); st.rerun()

            with st.expander("📝 Historial y Reportes"):
                if logs or inv:
                    df_mov = pd.DataFrame(logs)
                    df_stk = pd.DataFrame([{"Depo": v['deposito'], "Marca": v['marca'], "Código": k.split('_')[-1], "Cant": v['stock']} for k, v in inv.items()])
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        df_stk.to_excel(writer, index=False, sheet_name='STOCK ACTUAL')
                        df_mov.to_excel(writer, index=False, sheet_name='MOVIMIENTOS')
                    st.download_button("📥 EXCEL SEMANAL", buffer.getvalue(), f"Reporte_{datetime.now().strftime('%d_%m')}.xlsx", use_container_width=True)
                    st.divider()
                if st.button("🗑️ Limpiar Logs"): logs = []; guardar_todo(inv, config, logs); st.rerun()
                for l in logs[:10]: st.write(f"<small>{l['fecha']} | {l['detalle']}</small>", unsafe_allow_html=True)
