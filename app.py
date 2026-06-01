import streamlit as st
import folium
from streamlit_folium import st_folium
from supabase import create_client, Client
import json

# 1. Configuración de la pestaña del navegador
# 1. Configuración de la pestaña del navegador
st.set_page_config(page_title="UdeC Parking", layout="wide")
st.title("🚗 Waze Estacionamiento UdeC")
st.subheader("Biblioteca Central Luis David Cruz Ocampo")

# 2. Conectar a Supabase (Tus credenciales ya configuradas)
SUPABASE_URL = "https://zsessyqeipqtunfchfjc.supabase.co"
SUPABASE_KEY = "sb_publishable_Q4oEOqvEYSIj7nkc8dw4eA_P2pXUUR9"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 3. Función para traer los estados (libre/ocupado) desde la nube
def obtener_estados_supabase():
    res = supabase.table("estacionamientos").select("*").execute()
    # Lo transforma en un diccionario fácil de leer: { 'puesto_1': {'estado': 'libre', ...} }
    return {fila['id']: fila for fila in res.data}

estados_actuales = obtener_estados_supabase()

# 4. Cargar tus 12 coordenadas desde el archivo JSON
with open("mapa_udec.json", "r", encoding="utf-8") as f:
    datos_mapa = json.load(f)

# 5. Crear el mapa base centrado en la Biblioteca de la UdeC
# Usamos la coordenada del primer puesto para centrar la cámara
# 5. Crear el mapa base centrado en la Biblioteca con estilo Satelital Gratis
# 5. Crear el mapa base con zoom ultra cercano y bloqueado para que no se pierda
mapa = folium.Map(
    location=[-36.8326233, -73.034975], 
    zoom_start=21,          # <--- Subimos el zoom al máximo (21)
    max_zoom=22,            # Permite acercarse un pelo más si el satélite lo aguanta
    min_zoom=18,            # Evita que el usuario aleje el mapa y se pierda en Chile
    tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
    attr="Google Satellite"
)

# 6. Dibujar los 12 pines en el mapa según su estado real en Supabase
for feature in datos_mapa["features"]:
    puesto_id = feature["properties"]["id"]
    coordenadas = feature["geometry"]["coordinates"] # [longitud, latitud]
    
    # Buscar qué estado tiene este puesto en Supabase
    info_puesto = estados_actuales.get(puesto_id, {"estado": "libre", "comentario": ""})
    
    # Configurar el color: Libre -> Verde, Ocupado -> Rojo
    color_pin = "green" if info_puesto["estado"] == "libre" else "red"
    
    # Dibujar el marcador (Folium usa [latitud, longitud] al revés del JSON)
    folium.Marker(
        location=[coordenadas[1], coordenadas[0]],
        popup=f"<b>{puesto_id}</b><br>Estado: {info_puesto['estado']}<br>Nota: {info_puesto['comentario']}",
        icon=folium.Icon(color=color_pin, icon="car", prefix="fa")
    ).add_to(mapa)

# Mostrar el mapa interactivo en la pantalla web
# Mostrar el mapa interactivo mucho más grande
st_folium(mapa, width="100%", height=600)

st.write("---")

# 7. Formulario para que el alumno reporte en tiempo real
st.markdown("### 📢 ¿Estás en el campus? Reporta un cambio")

# Lista desplegable con los 12 puestos
puesto_seleccionado = st.selectbox("Selecciona el puesto:", [f"puesto_{i}" for i in range(1, 13)])
nuevo_estado = st.radio("¿Cuál es el estado actual?", ["libre", "ocupado"], horizontal=True)
comentario_alumno = st.text_input("Agregar una nota (opcional):", placeholder="Ej: Se va en 5 min, auto mal cuadrado...")

if st.button("Actualizar Disponibilidad", type="primary"):
    # Enviar los nuevos datos a Supabase
    supabase.table("estacionamientos").update({
        "estado": nuevo_estado,
        "comentario": comentario_alumno
    }).eq("id", puesto_seleccionado).execute()
    
    st.success(f"¡Gracias! El {puesto_seleccionado} ahora figura como {nuevo_estado}.")
    st.rerun() # Recarga la app automáticamente para actualizar el mapa en vivo