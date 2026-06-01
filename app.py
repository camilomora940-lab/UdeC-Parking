import streamlit as st
import folium
from streamlit_folium import st_folium
from supabase import create_client, Client
import json
import resend
from datetime import datetime, timezone

# 1. Configuración de la página (Modo Ancho Completo)
st.set_page_config(page_title="UdeC Parking", layout="wide", page_icon="🚗")

# 2. Conectar a Supabase
SUPABASE_URL = "https://zsessyqeipqtunfchfjc.supabase.co"
SUPABASE_KEY = "sb_publishable_Q4oEOqvEYSIj7nkc8dw4eA_P2pXUUR9"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- MANEJO DE SESIÓN EN STREAMLIT ---
if "usuario_autenticado" not in st.session_state:
    st.session_state["usuario_autenticado"] = False
if "perfil_usuario" not in st.session_state:
    st.session_state["perfil_usuario"] = None

# Si NO está autenticado, mostramos la pantalla de Login y Registro protegido
if not st.session_state["usuario_autenticado"]:
    st.markdown("<h2 style='text-align: center; color: #003366;'>🔐 Acceso Exclusivo UdeC</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #666666;'>Regístrate con tu correo institucional. Tus datos de contacto serán 100% privados.</p>", unsafe_allow_html=True)
    
    col_izq, col_centro, col_der = st.columns([1, 2, 1])
    
    with col_centro:
        tab_login, tab_registro = st.tabs(["🔑 Iniciar Sesión", "📝 Registrarse"])
        
        with tab_login:
            with st.form("form_login"):
                correo_log = st.text_input("Correo Institucional:", placeholder="ejemplo@udec.cl").strip().lower()
                clave_log = st.text_input("Contraseña:", type="password")
                boton_log = st.form_submit_button("Ingresar", type="primary", use_container_width=True)
                
                if boton_log:
                    if not correo_log.endswith("@udec.cl"):
                        st.error("❌ El correo debe pertenecer al dominio @udec.cl")
                    elif not correo_log or not clave_log:
                        st.error("❌ Por favor completa todos los campos.")
                    else:
                        try:
                            # 1. Autenticar usuario
                            res_auth = supabase.auth.sign_in_with_password({"email": correo_log, "password": clave_log})
                            user_id = res_auth.user.id
                            
                            # 2. Traer el perfil privado del alumno
                            res_perfil = supabase.table("perfiles").select("*").eq("id", user_id).execute()
                            
                            st.session_state["usuario_autenticado"] = True
                            if res_perfil.data:
                                st.session_state["perfil_usuario"] = res_perfil.data[0]
                            
                            st.success("¡Acceso correcto! Cargando mapa...")
                            st.rerun()
                        except Exception as e:
                            st.error("❌ Credenciales incorrectas o cuenta no verificada por correo.")

        with tab_registro:
            st.info("ℹ️ Al registrarte recibirás un link en tu Outlook UdeC para activar tu cuenta.")
            with st.form("form_registro"):
                correo_reg = st.text_input("Tu Correo @udec.cl:", placeholder="nombre@udec.cl").strip().lower()
                clave_reg = st.text_input("Crea una Contraseña (mínimo 6 caracteres):", type="password")
                
                st.markdown("---")
                st.markdown("##### 🛡️ Datos de Seguridad y Emergencia (Invisibles para otros alumnos)")
                patente_reg = st.text_input("Patente de tu Vehículo:", placeholder="ABCD12").strip().upper()
                telefono_reg = st.text_input("Teléfono Móvil:", placeholder="+56912345678").strip()
                
                boton_reg = st.form_submit_button("Crear Cuenta Alumno", use_container_width=True)
                
                if boton_reg:
                    if not correo_reg.endswith("@udec.cl"):
                        st.error("❌ Error: Solo se permiten correos oficiales @udec.cl")
                    elif len(clave_reg) < 6:
                        st.error("❌ La contraseña debe tener al menos 6 caracteres.")
                    elif not patente_reg or not telefono_reg:
                        st.error("❌ La patente y el teléfono son obligatorios para avisarte en caso de emergencias.")
                    else:
                        try:
                            # 1. Registrar en Supabase Auth
                            res_auth = supabase.auth.sign_up({"email": correo_reg, "password": clave_reg})
                            new_user_id = res_auth.user.id
                            
                            # 2. Insertar en la tabla espejo 'perfiles'
                            supabase.table("perfiles").insert({
                                "id": new_user_id,
                                "patente": patente_reg,
                                "telefono": telefono_reg
                            }).execute()
                            
                            st.success("¡Registro exitoso! 📧 Revisa tu correo de la UdeC para confirmar tu cuenta antes de iniciar sesión.")
                        except Exception as e:
                            st.error(f"❌ Error al registrar. Asegúrate de que la patente no esté registrada por otra persona.")
                            
    st.stop()

# --- SI LLEGA ACÁ, EL ALUMNO YA ESTÁ LOGUEADO ---

col_tit, col_logout = st.columns([8, 2])
with col_tit:
    st.markdown("<h1 style='color: #003366; margin-top: -20px;'>🚗 Waze Estacionamiento UdeC</h1>", unsafe_allow_html=True)
    st.markdown("<h4 style='color: #666666;'>Biblioteca Central Luis David Cruz Ocampo</h4>", unsafe_allow_html=True)

with col_logout:
    patente_barra = st.session_state["perfil_usuario"].get("patente", "SIN PATENTE") if st.session_state["perfil_usuario"] else "Usuario"
    st.write(f"👤 Patente: **{patente_barra}**")
    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        supabase.auth.sign_out()
        st.session_state["usuario_autenticado"] = False
        st.session_state["perfil_usuario"] = None
        st.rerun()

st.write("---")

# 3. Función para obtener estados de estacionamientos
def obtener_estados_supabase():
    res = supabase.table("estacionamientos").select("*").execute()
    datos = {}
    ahora = datetime.now(timezone.utc)
    
    for fila in res.data:
        tiempo_texto = "Sin reportes"
        if fila.get("actualizado_en"):
            dt_reporte = datetime.fromisoformat(fila["actualizado_en"].replace("Z", "+00:00"))
            diferencia = ahora - dt_reporte
            minutos = int(diferencia.total_seconds() / 60)
            
            if minutos < 1:
                tiempo_texto = "Hace un momento"
            elif minutos < 60:
                tiempo_texto = f"Hace {minutos} min"
            else:
                horas = minutos // 60
                tiempo_texto = f"Hace {horas} h"
                
        fila["tiempo_transcurrido"] = tiempo_texto
        datos[fila['id']] = fila
    return datos

estados_actuales = obtener_estados_supabase()

with open("mapa_udec.json", "r", encoding="utf-8") as f:
    datos_mapa = json.load(f)

# 4. TARJETAS MÉTRICAS (KPIs)
total_puestos = len(estados_actuales)
libres = sum(1 for p in estados_actuales.values() if p["estado"] == "libre")
ocupados = total_puestos - libres

met1, met2, met3 = st.columns(3)
with met1:
    st.metric(label="🟢 Puestos Disponibles", value=f"{libres} / {total_puestos}")
with met2:
    st.metric(label="🔴 Puestos Ocupados", value=ocupados)
with met3:
    estado_campus = "Despejado" if libres > 6 else "Normal" if libres > 2 else "Congestionado"
    st.metric(label="📊 Estado del Sector", value=estado_campus)

st.write("---")

# 5. DISEÑO EN PESTAÑAS
tab_mapa, tab_reportar, tab_emergencia, tab_perfil = st.tabs([
    "🗺️ Ver Mapa en Vivo", 
    "📢 Reportar Disponibilidad", 
    "⚠️ Alerta de Emergencia",
    "👤 Mi Perfil"
])

with tab_mapa:
    st.markdown("### Estado en tiempo real")
    st.caption("Pines Azules = Disponibles | Pines Rojos = Ocupados. Haz clic en un auto para ver la patente.")
    
    mapa = folium.Map(
        location=[-36.8326233, -73.034975], zoom_start=21, max_zoom=22, min_zoom=18,
        tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", attr="Google Satellite"
    )

    for feature in datos_mapa["features"]:
        puesto_id = feature["properties"]["id"]
        coordenadas = feature["geometry"]["coordinates"]
        
        info_puesto = estados_actuales.get(puesto_id, {"estado": "libre", "comentario": "", "tiempo_transcurrido": "---", "patente": ""})
        
        color_pin = "blue" if info_puesto["estado"] == "libre" else "red"
        icon_car = "check" if info_puesto["estado"] == "libre" else "times"
        
        # El mapa usa .get() de forma segura y nunca expone teléfonos ni nombres
        patente_puesto = info_puesto.get("patente", "")
        detalles_patente = f"<br><b>Patente:</b> {patente_puesto}" if patente_puesto else ""
        
        popup_html = f"""
        <div style='font-family: Arial, sans-serif; width: 140px;'>
            <b style='color: #003366;'>{puesto_id.upper().replace('_', ' ')}</b><br>
            <b>Estado:</b> {info_puesto['estado'].upper()}
            {detalles_patente}<br>
            <small style='color: gray;'>⏱️ {info_puesto['tiempo_transcurrido']}</small><br>
            <p style='margin: 5px 0 0 0; font-size: 11px; color: #333;'><i>{info_puesto['comentario']}</i></p>
        </div>
        """
        
        folium.Marker(
            location=[coordenadas[1], coordenadas[0]],
            popup=folium.Popup(popup_html, max_width=150),
            icon=folium.Icon(color=color_pin, icon=icon_car, prefix="fa")
        ).add_to(mapa)

    st_folium(mapa, width="100%", height=550)

with tab_reportar:
    st.markdown("### 📢 Reportar un puesto")
    
    with st.container(border=True):
        col_puesto, col_estado = st.columns(2)
        with col_puesto:
            puesto_seleccionado = st.selectbox("¿Qué puesto estás viendo?", [f"puesto_{i}" for i in range(1, 13)], format_func=lambda x: x.upper().replace("_", " "))
        with col_estado:
            nuevo_estado = st.radio("¿Cuál es el estado actual?", ["libre", "ocupado"], horizontal=True)
            
        comentario_alumno = st.text_input("Agregar una nota rápida (opcional):", placeholder="Ej: Auto mal cuadrado, se va en breve...")
        
        if st.button("🚀 Publicar Reporte en Vivo", type="primary", use_container_width=True):
            patente_vehiculo = ""
            if nuevo_estado == "ocupado" and st.session_state["perfil_usuario"]:
                patente_vehiculo = st.session_state["perfil_usuario"].get("patente", "")
                
            supabase.table("estacionamientos").update({
                "estado": nuevo_estado,
                "comentario": comentario_alumno,
                "actualizado_en": datetime.now(timezone.utc).isoformat(),
                "patente": patente_vehiculo
            }).eq("id", puesto_seleccionado).execute()
            
            st.success("¡Reporte actualizado con éxito!")
            st.rerun()

with tab_emergencia:
    st.markdown("### ⚠️ Notificar un problema al dueño del auto")
    st.write("Se enviará un correo automático al dueño del vehículo de forma 100% privada.")
    
    resend.api_key = "re_jmB3n8Pm_FeybdcnKiV7miv5mZtJ75BeH"

    with st.container(border=True):
        patente_buscar = st.text_input("Patente del auto con problemas:", placeholder="ABCD12").strip().upper()
        tipo_problema = st.selectbox("¿Cuál es el problema?", [
            "Dejaste las luces encendidas 💡",
            "Tu vehículo está bloqueando la pasada / mal estacionado 🚧",
            "Tienes una ventana completamente abajo o mal cerrada 🪟",
            "Tu auto tiene una alarma sonando hace mucho rato 🚨"
        ])
        
        if st.button("📧 Enviar Alerta por Correo", type="primary"):
            if not patente_buscar:
                st.error("Por favor ingresa una patente válida.")
            else:
                # DIAGNÓSTICO: Vamos a ver qué responde la base de datos exactamente
                res_buscar = supabase.table("perfiles").select("*").eq("patente", patente_buscar).execute()
                
                # Esto imprimirá un cuadro temporal en tu app con el resultado real de la BD
                st.info(f"🔍 Diagnóstico BD: {res_buscar.data}")
                
                if res_buscar.data:
                    user_id_dueno = res_buscar.data[0]["id"]
                    
                    try:
                        params = {
                            "from": "Waze UdeC <onboarding@resend.dev>",
                            "to": ["camilomora940@gmail.com"], # Usa aquí el correo que registraste en Resend para la prueba
                            "subject": f"🚨 Alerta de Emergencia - Patente {patente_buscar}",
                            "html": f"""
                                <h3>Hola, compañero de la UdeC</h3>
                                <p>Alguien ha reportado un problema con tu vehículo estacionado en la Biblioteca:</p>
                                <p><b>Problema:</b> {tipo_problema}</p>
                                <hr>
                                <p><small>Este es un mensaje automático de Waze UdeC. No compartimos tu información personal.</small></p>
                            """
                        }
                        resend.Emails.send(params)
                        st.success(f"¡Alerta enviada! El dueño del vehículo {patente_buscar} recibirá un correo en instantes.")
                    except Exception as e:
                        st.error(f"Error al enviar el correo: {e}")
                else:
                    st.error("La patente ingresada no está registrada en el sistema.")
with tab_perfil:
    st.markdown("### 👤 Configuración de mi Perfil UdeC")
    st.write("Aquí puedes revisar y actualizar los datos vinculados a tu cuenta institucional.")
    
    if st.session_state["perfil_usuario"]:
        perfil = st.session_state["perfil_usuario"]
        user_id_actual = perfil.get("id")
        
        with st.container(border=True):
            st.markdown("#### 🔒 Mis Datos Registrados")
            
            col_pat_perfil, col_tel_perfil = st.columns(2)
            with col_pat_perfil:
                patente_editada = st.text_input("Patente de tu Vehículo:", value=perfil.get("patente", ""), max_chars=6).strip().upper()
            with col_tel_perfil:
                telefono_editado = st.text_input("Teléfono Móvil de Contacto:", value=perfil.get("telefono", "")).strip()
            
            st.write("")
            if st.button("💾 Actualizar mis Datos", type="primary", use_container_width=True):
                if not patente_editada or not telefono_editado:
                    st.error("❌ Los campos no pueden quedar vacíos.")
                else:
                    try:
                        supabase.table("perfiles").update({
                            "patente": patente_editada,
                            "telefono": telefono_editado
                        }).eq("id", user_id_actual).execute()
                        
                        st.session_state["perfil_usuario"]["patente"] = patente_editada
                        st.session_state["perfil_usuario"]["telefono"] = telefono_editado
                        
                        st.success("¡Perfil actualizado con éxito!")
                        st.rerun()
                    except Exception as e:
                        st.error("❌ Error al actualizar. Esa patente ya puede estar en uso.")
    else:
        st.error("No se pudo cargar la información. Cierra sesión e intenta ingresar nuevamente.")
