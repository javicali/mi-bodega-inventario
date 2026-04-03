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
config = cargar_json(ARCHIVO_CONF, {"usuarios": {"ADMIN": "admin123"}, "depositos": ["SETAR"], "marcas": ["IRUN", "BOOTY"]})
logs = cargar_json(ARCHIVO_LOG, [])

if 'modo_panel' not in st.session_state: st.session_state.modo_panel = False
if 'edit_mode' not in st.session_state: st.session_state.edit_mode = False

# --- FUNCIÓN TARJETA EDICIÓN ---
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

# --- LÓGICA DE PANTALLAS ---
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
                mensaje = f"**{busq}** ({v['marca']}) en **{v['deposito']}**: {v['stock']} cajas"
                if v['stock'] > 0: st.success(f"✅ {mensaje}")
                else: st.error(f"🚨 AGOTADO: {mensaje}")
        elif busq: st.warning("⚠️ Código no registrado.")
    
    st.divider()
    if st.checkbox("👁️ Ver Stock General"):
        dep_v = st.selectbox("Depósito:", config["depositos"], key="view_dep")
        tabs = st.tabs(config["marcas"])
        for i, m in enumerate(config["marcas"]):
            with tabs[i]:
                items = {k: v for k, v in inv.items() if v.get('marca')==m and v.get('deposito')==dep_v and v.get('stock',0)>0}
                if not items: st.write("Sin existencias.")
                for kid, info in items.items(): st.write(f"**{kid.split('_')[-1]}**: {info['stock']} cajas")

else:
    st.title("🛠️ Panel de Modificación")
    busq_m = st.text_input("🔎 BUSCAR PARA EDITAR:", key="edit_search_p").upper().strip()
    if busq_m:
        items_f = {k: v for k, v in inv.items() if (k.split("_", 1)[1] if "_" in k else k) == busq_m}
        if items_f:
            for id_f, info in items_f.items(): mostrar_item_edicion(id_f, info, "p_busq")
        else: st.error("No se encontró el código.")
    
    st.divider()
    dep_sel = st.selectbox("📍 Seleccione Depósito:", config["depositos"], key="p_dep_sel")
    nombres_tabs = config["marcas"] + ["⚠️ AGOTADOS"]
    tabs_e = st.tabs(nombres_tabs)
    
    for i, m_e in enumerate(nombres_tabs):
        with tabs_e[i]:
            if m_e == "⚠️ AGOTADOS":
                items_p = {k: v for k, v in inv.items() if v.get('stock', 0) == 0 and v.get('deposito') == dep_sel}
            else:
                items_p = {k: v for k, v in inv.items() if v.get('marca') == m_e and v.get('deposito') == dep_sel and v.get('stock', 0) > 0}
            
            if items_p:
                for id_f, info in sorted(items_p.items()): mostrar_item_edicion(id_f, info, f"p_tab_{i}")
            else: st.write(f"Sin productos en {m_e}.")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔐 Acceso")
    if not st.session_state.edit_mode:
        u = st.selectbox("Usuario", list(config["usuarios"].keys()), key="login_u")
        p = st.text_input("Clave", type="password", key="login_p")
        if st.button("🔓 Entrar"):
            if config["usuarios"].get(u) == p:
                st.session_state.edit_mode, st.session_state.usuario_actual = True, u
                st.rerun()
    else:
        st.success(f"👤 {st.session_state.usuario_actual}")
        txt_m = "🏠 VISTA INICIO" if st.session_state.modo_panel else "⚙️ PANEL CONTROL"
        if st.button(txt_m, use_container_width=True):
            st.session_state.modo_panel = not st.session_state.modo_panel
            st.rerun()
        if st.button("🔒 Salir", use_container_width=True):
            st.session_state.edit_mode, st.session_state.modo_panel = False, False
            st.rerun()

        st.divider()

        with st.expander("🆕 Nuevo Código"):
            rm = st.selectbox("Marca", config["marcas"], key="reg_m")
            rc = st.text_input("Código", key="reg_c").upper().strip()
            rd = st.selectbox("Depósito", config["depositos"], key="reg_d")
            if st.button("💾 Guardar Nuevo"):
                if rc:
                    inv[f"{rd}_{rc}"] = {"marca": rm, "deposito": rd, "stock": 0}
                    registrar_log(logs, st.session_state.usuario_actual, "CREACION", f"Creó {rc}")
                    guardar_todo(inv, config, logs); st.rerun()

        if st.session_state.usuario_actual == "ADMIN":
            with st.expander("👥 Gestión de Usuarios"):
                for user in list(config["usuarios"].keys()):
                    c1, c2 = st.columns([3, 1])
                    c1.write(user)
                    if user != "ADMIN" and c2.button("🗑️", key=f"del_u_{user}"):
                        del config["usuarios"][user]; guardar_todo(inv, config, logs); st.rerun()
                nu = st.text_input("Nuevo Usuario").upper()
                np = st.text_input("Clave", type="password")
                if st.button("💾 Crear Usuario"):
                    if nu: config["usuarios"][nu] = np; guardar_todo(inv, config, logs); st.rerun()

            with st.expander("🏷️ Gestión de Marcas"):
                for m in config["marcas"]:
                    c1, c2 = st.columns([3, 1])
                    c1.write(m)
                    if c2.button("🗑️", key=f"del_mar_{m}"):
                        config["marcas"].remove(m); guardar_todo(inv, config, logs); st.rerun()
                nm = st.text_input("Nueva Marca").upper()
                if st.button("➕ Añadir Marca"):
                    if nm and nm not in config["marcas"]: config["marcas"].append(nm); guardar_todo(inv, config, logs); st.rerun()

            with st.expander("🏘️ Gestión de Depósitos"):
                for d in config["depositos"]:
                    c1, c2, c3 = st.columns([2, 0.5, 0.5])
                    c1.write(f"📍 {d}")
                    if c2.button("✏️", key=f"ed_dep_b_{d}"): st.session_state[f"edit_dep_{d}"] = True
                    if c3.button("🗑️", key=f"del_dep_{d}"):
                        config["depositos"].remove(d); guardar_todo(inv, config, logs); st.rerun()
                    
                    if st.session_state.get(f"edit_dep_{d}"):
                        nuevo_n = st.text_input("Nuevo nombre:", value=d, key=f"nn_{d}").upper().strip()
                        ce1, ce2 = st.columns(2)
                        if ce1.button("✅ Ok", key=f"sv_d_{d}"):
                            if nuevo_n and nuevo_n not in config["depositos"]:
                                config["depositos"][config["depositos"].index(d)] = nuevo_n
                                # Actualizar productos (Llave y Valor)
                                nuevas_llaves = {}
                                for k, v in inv.items():
                                    if v["deposito"] == d:
                                        v["deposito"] = nuevo_n
                                        nuevas_llaves[f"{nuevo_n}_{k.split('_', 1)[1]}"] = v
                                    else: nuevas_llaves[k] = v
                                inv.clear(); inv.update(nuevas_llaves)
                                registrar_log(logs, st.session_state.usuario_actual, "RENOMBRAR", f"{d} -> {nuevo_n}")
                                guardar_todo(inv, config, logs)
                                del st.session_state[f"edit_dep_{d}"]; st.rerun()
                        if ce2.button("❌", key=f"cn_d_{d}"):
                            del st.session_state[f"edit_dep_{d}"]; st.rerun()

                nd = st.text_input("Nuevo Depósito").upper()
                if st.button("➕ Añadir Depo"):
                    if nd and nd not in config["depositos"]: config["depositos"].append(nd); guardar_todo(inv, config, logs); st.rerun()

            with st.expander("🔄 Traslado entre Depósitos"):
                t_cod = st.text_input("Código a trasladar", key="tr_c").upper().strip()
                t_origen = st.selectbox("Desde:", config["depositos"], key="t_ori")
                t_destino = st.selectbox("Hacia:", config["depositos"], key="t_des")
                t_cant = st.number_input("Cantidad", min_value=1, value=1, key="tr_q")
                if st.button("Confirmar Traslado"):
                    id_ori, id_des = f"{t_origen}_{t_cod}", f"{t_destino}_{t_cod}"
                    if id_ori in inv and inv[id_ori]["stock"] >= t_cant:
                        inv[id_ori]["stock"] -= t_cant
                        if id_des not in inv: inv[id_des] = {"marca": inv[id_ori]["marca"], "deposito": t_destino, "stock": 0}
                        inv[id_des]["stock"] += t_cant
                        registrar_log(logs, st.session_state.usuario_actual, "TRASLADO", f"{t_cant} {t_cod}")
                        guardar_todo(inv, config, logs); st.rerun()

            with st.expander("📝 Historial"):
                if st.button("🗑️ Limpiar Historial"): logs = []; guardar_todo(inv, config, logs); st.rerun()
                for l in logs: st.write(f"<small>{l['fecha']} | {l['usuario']} | {l['detalle']}</small>", unsafe_allow_html=True)
