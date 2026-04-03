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

st.markdown("""<style>
    .block-container {padding-top: 1rem;}
    .stButton>button {padding: 0.2rem 0.5rem; width: 100%;}
    small { color: #888; }
</style>""", unsafe_allow_html=True)

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
            key_aviso = f"aviso_{sufijo}_{id_f}"
            if key_aviso in st.session_state:
                tipo, msg = st.session_state[key_aviso]
                if tipo == "SUMA": st.success(msg)
                elif tipo == "RESTA": st.warning(msg)
                if st.button("Aceptar ✅", key=f"clear_{sufijo}_{id_f}"):
                    del st.session_state[key_aviso]
                    st.rerun()
            else:
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
                            st.session_state[key_aviso] = ("SUMA", f"¡Aumentado! +{cant}")
                        elif estado == "R": 
                            if inv[id_f]["stock"] >= cant:
                                inv[id_f]["stock"] -= cant
                                registrar_log(logs, st.session_state.usuario_actual, "RESTA", f"-{cant} {cod_l}")
                                st.session_state[key_aviso] = ("RESTA", f"¡Descontado! -{cant}")
                        elif estado == "B": 
                            registrar_log(logs, st.session_state.usuario_actual, "BORRAR", f"Eliminó {cod_l}")
                            del inv[id_f]
                        
                        guardar_todo(inv, config, logs)
                        del st.session_state[f"conf_{sufijo}_{id_f}"]
                        st.rerun()

# --- INTERFAZ PRINCIPAL ---
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
                msg = f"**{busq}** ({v['marca']}) en **{v['deposito']}**: {v['stock']} unidades"
                if v['stock'] > 0: st.success(f"✅ {msg}")
                else: st.error(f"🚨 AGOTADO: {msg}")
        elif busq:
            st.warning("⚠️ Código no registrado.")
    
    st.divider()
    if st.checkbox("👁️ Ver Stock General"):
        d_v = st.selectbox("Seleccione Depósito:", config["depositos"])
        tbs = st.tabs(config["marcas"])
        for i, m in enumerate(config["marcas"]):
            with tbs[i]:
                items = {k: v for k, v in inv.items() if v.get('marca')==m and v.get('deposito')==d_v and v.get('stock',0)>0}
                if not items: st.write("_Sin existencias._")
                for kid, info in items.items(): st.write(f"**{kid.split('_')[-1]}**: {info['stock']} unidades")

else:
    st.title("🛠️ Panel de Control")
    b_p = st.text_input("🔎 BUSCAR PARA EDITAR:").upper().strip()
    if b_p:
        res_p = {k: v for k, v in inv.items() if (k.split("_", 1)[1] if "_" in k else k) == b_p}
        for k, v in res_p.items(): mostrar_item_edicion(k, v, "p_busq")
    
    st.divider()
    dep_p = st.selectbox("📍 Depósito de trabajo:", config["depositos"])
    nombres_tabs = config["marcas"] + ["⚠️ AGOTADOS"]
    tabs_p = st.tabs(nombres_tabs)
    for i, m_p in enumerate(nombres_tabs):
        with tabs_p[i]:
            if m_p == "⚠️ AGOTADOS":
                it_p = {k: v for k, v in inv.items() if v.get('stock',0)==0 and v.get('deposito')==dep_p}
            else:
                it_p = {k: v for k, v in inv.items() if v.get('marca')==m_p and v.get('deposito')==dep_p and v.get('stock',0)>0}
            if it_p:
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
            st.session_state.edit_mode = False; st.session_state.modo_panel = False; st.rerun()

        st.divider()
        with st.expander("🆕 Nuevo Código"):
            n_m = st.selectbox("Marca", config["marcas"])
            n_c = st.text_input("Código").upper().strip()
            n_d = st.selectbox("Depósito", config["depositos"])
            if st.button("💾 Crear"):
                if n_c:
                    inv[f"{n_d}_{n_c}"] = {"marca": n_m, "deposito": n_d, "stock": 0}
                    registrar_log(logs, st.session_state.usuario_actual, "CREACION", f"Nuevo: {n_c}")
                    guardar_todo(inv, config, logs); st.rerun()

        if st.session_state.usuario_actual.upper() == "ADMIN":
            st.markdown("### 👑 Administración")
            
            with st.expander("🏘️ Gestión de Depósitos"):
                st.write("**Lista Actual:**")
                for d in config["depositos"]:
                    c1, c2 = st.columns([3, 1])
                    c1.write(f"📍 {d}")
                    if c2.button("🗑️", key=f"del_dep_{d}"):
                        config["depositos"].remove(d)
                        guardar_todo(inv, config, logs); st.rerun()
                
                st.divider()
                st.write("**Renombrar Depósito:**")
                d_viejo = st.selectbox("Seleccionar para cambiar:", config["depositos"], key="sel_old")
                d_nuevo = st.text_input("Nombre Nuevo:").upper().strip()
                if st.button("Aplicar Cambio de Nombre"):
                    if d_nuevo and d_nuevo not in config["depositos"]:
                        # 1. Cambiar en la lista de config
                        idx = config["depositos"].index(d_viejo)
                        config["depositos"][idx] = d_nuevo
                        # 2. Cambiar en todos los productos del inventario
                        nuevo_inv = {}
                        for k, v in inv.items():
                            if v["deposito"] == d_viejo:
                                v["deposito"] = d_nuevo
                                codigo_real = k.split("_", 1)[1] if "_" in k else k
                                nuevo_inv[f"{d_nuevo}_{codigo_real}"] = v
                            else:
                                nuevo_inv[k] = v
                        inv.clear()
                        inv.update(nuevo_inv)
                        registrar_log(logs, "ADMIN", "RENOMBRAR", f"{d_viejo} -> {d_nuevo}")
                        guardar_todo(inv, config, logs); st.rerun()
                
                st.divider()
                nd = st.text_input("Añadir Depósito Nuevo").upper().strip()
                if st.button("➕ Añadir"):
                    if nd and nd not in config["depositos"]:
                        config["depositos"].append(nd)
                        guardar_todo(inv, config, logs); st.rerun()

            with st.expander("🏷️ Gestión de Marcas"):
                for m in config["marcas"]:
                    c1, c2 = st.columns([3, 1])
                    c1.write(m)
                    if c2.button("🗑️", key=f"del_mar_{m}"):
                        config["marcas"].remove(m)
                        guardar_todo(inv, config, logs); st.rerun()
                nm = st.text_input("Nueva Marca").upper().strip()
                if st.button("➕ Marca"):
                    if nm and nm not in config["marcas"]: config["marcas"].append(nm); guardar_todo(inv, config, logs); st.rerun()

            with st.expander("🔄 Traslados"):
                tc, to, td = st.text_input("Cod").upper().strip(), st.selectbox("Desde", config["depositos"]), st.selectbox("Hacia", config["depositos"])
                tq = st.number_input("Cant", min_value=1, value=1)
                if st.button("Confirmar Traslado"):
                    io, id_d = f"{to}_{tc}", f"{td}_{tc}"
                    if io in inv and inv[io]["stock"] >= tq:
                        inv[io]["stock"] -= tq
                        if id_d not in inv: inv[id_d] = {"marca": inv[io]["marca"], "deposito": td, "stock": 0}
                        inv[id_d]["stock"] += tq
                        registrar_log(logs, st.session_state.usuario_actual, "TRASLADO", f"{tq} {tc} ({to}->{td})")
                        guardar_todo(inv, config, logs); st.rerun()

            with st.expander("📝 Historial y Reportes"):
                if inv:
                    df_stk = pd.DataFrame([{"Depo": v['deposito'], "Marca": v['marca'], "Código": k.split('_')[-1], "Cant": v['stock']} for k, v in inv.items()])
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        df_stk.to_excel(writer, index=False, sheet_name='STOCK')
                    st.download_button("📥 DESCARGAR EXCEL", buffer.getvalue(), "Inventario.xlsx", use_container_width=True)
                
                for l in logs[:15]:
                    st.write(f"**{l['usuario']}**: {l['detalle']}  \n<small>{l['fecha']}</small>", unsafe_allow_html=True)
                    st.divider()
