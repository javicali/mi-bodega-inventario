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

# Estilos visuales
st.markdown("""<style>
    .block-container {padding-top: 1rem;}
    .stButton>button {padding: 0.2rem 0.5rem; width: 100%;}
    small { color: #888; }
</style>""", unsafe_allow_html=True)

# Cargar datos
inv = cargar_json(ARCHIVO_DB, {})
config = cargar_json(ARCHIVO_CONF, {"usuarios": {"ADMIN": "admin123"}, "depositos": ["SETAR"], "marcas": ["IRUN", "BOOTY"]})
logs = cargar_json(ARCHIVO_LOG, [])

if 'modo_panel' not in st.session_state: st.session_state.modo_panel = False
if 'edit_mode' not in st.session_state: st.session_state.edit_mode = False

# --- FUNCIÓN TARJETA DE EDICIÓN (WIDGETS) ---
def mostrar_item_edicion(id_f, info, sufijo):
    cod_l = id_f.split("_", 1)[1] if "_" in id_f else id_f
    with st.container(border=True):
        c1, c2, c3 = st.columns([1.5, 1, 2.2])
        c1.markdown(f"**{cod_l}**\n<small>{info['marca']} | {info['deposito']}</small>", unsafe_allow_html=True)
        c2.markdown(f"📦 **{info['stock']}**\n<small>unidades</small>", unsafe_allow_html=True)
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
                    del st.session_state[f"conf_{sufijo}_{id_f}"]; st.rerun()

# --- LÓGICA DE INTERFAZ PRINCIPAL ---
if not st.session_state.modo_panel:
    st.title("🏢 Consulta de Inventario")
    busq = st.text_input("🔍 Buscar código rápido:", placeholder="Escriba el código...").upper().strip()
    if busq:
        res = {k: v for k, v in inv.items() if (k.split("_", 1)[1] if "_" in k else k) == busq}
        if res:
            for k, v in res.items():
                msg = f"**{busq}** ({v['marca']}) en **{v['deposito']}**: {v['stock']} cajas"
                if v['stock'] > 0: st.success(f"✅ {msg}")
                else: st.error(f"🚨 AGOTADO: {msg}")
        else: st.warning("⚠️ Código no encontrado.")
    
    st.divider()
    if st.checkbox("👁️ Ver Stock General por Depósito"):
        d_v = st.selectbox("Seleccione Depósito:", config["depositos"])
        tbs = st.tabs(config["marcas"])
        for i, m in enumerate(config["marcas"]):
            with tbs[i]:
                items = {k: v for k, v in inv.items() if v.get('marca')==m and v.get('deposito')==d_v and v.get('stock',0)>0}
                if not items: st.write("_Sin existencias disponibles._")
                for kid, info in items.items(): st.write(f"**{kid.split('_')[-1]}**: {info['stock']} unidades")

else:
    st.title("🛠️ Panel de Control y Modificación")
    # Buscador interno
    b_p = st.text_input("🔎 BUSCAR PARA EDITAR (Cualquier depo):").upper().strip()
    if b_p:
        res_p = {k: v for k, v in inv.items() if (k.split("_", 1)[1] if "_" in k else k) == b_p}
        for k, v in res_p.items(): mostrar_item_edicion(k, v, "p_busq")
    
    st.divider()
    # Pestañas por depósito
    dep_p = st.selectbox("📍 Depósito de trabajo:", config["depositos"])
    tabs_p = st.tabs(config["marcas"] + ["⚠️ AGOTADOS"])
    for i, m_p in enumerate(config["marcas"] + ["⚠️ AGOTADOS"]):
        with tabs_p[i]:
            if m_p == "⚠️ AGOTADOS":
                it_p = {k: v for k, v in inv.items() if v.get('stock',0)==0 and v.get('deposito')==dep_p}
            else:
                it_p = {k: v for k, v in inv.items() if v.get('marca')==m_p and v.get('deposito')==dep_p and v.get('stock',0)>0}
            
            if it_p:
                for k, v in sorted(it_p.items()): mostrar_item_edicion(k, v, f"p_tab_{i}")
            else: st.write(f"No hay registros en esta sección.")

# --- SIDEBAR (GESTIÓN) ---
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
        # 1. NUEVO CÓDIGO
        with st.expander("🆕 Nuevo Código"):
            n_m = st.selectbox("Marca", config["marcas"], key="n_m")
            n_c = st.text_input("Código", key="n_c").upper().strip()
            n_d = st.selectbox("Depósito", config["depositos"], key="n_d")
            if st.button("💾 Crear"):
                if n_c:
                    inv[f"{n_d}_{n_c}"] = {"marca": n_m, "deposito": n_d, "stock": 0}
                    registrar_log(logs, st.session_state.usuario_actual, "CREACION", f"Nuevo: {n_c}")
                    guardar_todo(inv, config, logs); st.rerun()

        if st.session_state.usuario_actual == "ADMIN":
            # 2. USUARIOS
            with st.expander("👥 Usuarios"):
                for us in list(config["usuarios"].keys()):
                    c1, c2 = st.columns([3, 1])
                    c1.write(us)
                    if us != "ADMIN" and c2.button("🗑️", key=f"du_{us}"):
                        del config["usuarios"][us]; guardar_todo(inv, config, logs); st.rerun()
                nu, np = st.text_input("Nombre"), st.text_input("Pass", type="password")
                if st.button("➕ Crear Usuario"):
                    if nu: config["usuarios"][nu.upper()] = np; guardar_todo(inv, config, logs); st.rerun()

            # 3. MARCAS
            with st.expander("🏷️ Marcas"):
                for m_l in config["marcas"]:
                    c1, c2 = st.columns([3, 1])
                    c1.write(m_l)
                    if c2.button("🗑️", key=f"dm_{m_l}"):
                        config["marcas"].remove(m_l); guardar_todo(inv, config, logs); st.rerun()
                nm = st.text_input("Nueva Marca").upper().strip()
                if st.button("➕ Añadir Marca"):
                    if nm and nm not in config["marcas"]: config["marcas"].append(nm); guardar_todo(inv, config, logs); st.rerun()

            # 4. DEPÓSITOS (CON EDICIÓN)
            with st.expander("🏘️ Depósitos"):
                for d_l in config["depositos"]:
                    c1, c2, c3 = st.columns([2, 0.5, 0.5])
                    c1.write(f"📍 {d_l}")
                    if c2.button("✏️", key=f"ed_{d_l}"): st.session_state[f"editing_{d_l}"] = True
                    if c3.button("🗑️", key=f"dd_{d_l}"):
                        config["depositos"].remove(d_l); guardar_todo(inv, config, logs); st.rerun()
                    
                    if st.session_state.get(f"editing_{d_l}"):
                        nuevo_nombre = st.text_input("Nuevo nombre:", value=d_l, key=f"nn_{d_l}").upper().strip()
                        ce1, ce2 = st.columns(2)
                        if ce1.button("✅ Ok", key=f"okd_{d_l}"):
                            config["depositos"][config["depositos"].index(d_l)] = nuevo_nombre
                            ni = {}
                            for k, v in inv.items():
                                if v["deposito"] == d_l:
                                    v["deposito"] = nuevo_nombre
                                    ni[f"{nuevo_nombre}_{k.split('_',1)[1]}"] = v
                                else: ni[k] = v
                            inv.clear(); inv.update(ni); guardar_todo(inv, config, logs); st.rerun()
                        if ce2.button("❌", key=f"cxd_{d_l}"): del st.session_state[f"editing_{d_l}"]; st.rerun()
                nd = st.text_input("Añadir Depo").upper().strip()
                if st.button("➕"): config["depositos"].append(nd); guardar_todo(inv, config, logs); st.rerun()

            # 5. TRASLADOS
            with st.expander("🔄 Traslados"):
                tc, to, td = st.text_input("Código").upper().strip(), st.selectbox("Desde", config["depositos"]), st.selectbox("Hacia", config["depositos"])
                tq = st.number_input("Cant", min_value=1, value=1)
                if st.button("Confirmar Traslado"):
                    io, id = f"{to}_{tc}", f"{td}_{tc}"
                    if io in inv and inv[io]["stock"] >= tq:
                        inv[io]["stock"] -= tq
                        if id not in inv: inv[id] = {"marca": inv[io]["marca"], "deposito": td, "stock": 0}
                        inv[id]["stock"] += tq
                        registrar_log(logs, st.session_state.usuario_actual, "TRASLADO", f"{tq} {tc} ({to}->{td})")
                        guardar_todo(inv, config, logs); st.rerun()

            # 6. HISTORIAL Y EXCEL
            with st.expander("📝 Historial y Reportes"):
                if logs or inv:
                    # Preparar Excel
                    df_mov = pd.DataFrame(logs)
                    df_stk = pd.DataFrame([{"Depo": v['deposito'], "Marca": v['marca'], "Código": k.split('_')[-1], "Cant": v['stock']} for k, v in inv.items()])
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        df_stk.to_excel(writer, index=False, sheet_name='STOCK ACTUAL')
                        df_mov.to_excel(writer, index=False, sheet_name='MOVIMIENTOS')
                    
                    st.download_button("📥 DESCARGAR EXCEL SEMANAL", buffer.getvalue(), f"Reporte_{datetime.now().strftime('%d_%m')}.xlsx", use_container_width=True)
                    st.divider()
                if st.button("🗑️ Limpiar Logs"): logs = []; guardar_todo(inv, config, logs); st.rerun()
                for l in logs[:15]: st.write(f"<small>{l['fecha']} | {l['detalle']}</small>", unsafe_allow_html=True)
