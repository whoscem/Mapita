import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import numpy as np

# Configuración de la página
st.set_page_config(page_title="Rutas Logísticas", layout="wide")

# Título y CSS para profesionalismo
st.markdown("""
    <style>
    .big-font { font-size:30px !important; font-weight: bold; }
    .metric-card { background-color: #f0f2f6; border-radius: 10px; padding: 10px; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="big-font">🚛 Dashboard de Optimización de Rutas Escolares</p>', unsafe_allow_html=True)

# 1. Carga de Datos y Session State (Para recordar los checks)
@st.cache_data
def load_data():
    df = pd.read_csv('escuelas.csv', delimiter=';') # Asegúrate que el archivo esté en la misma carpeta
    # Limpieza básica
    df['LONGITUD'] = pd.to_numeric(df['LONGITUD'], errors='coerce')
    df['LATITUD'] = pd.to_numeric(df['LATITUD'], errors='coerce')
    df = df.dropna(subset=['LATITUD', 'LONGITUD'])
    return df

if 'visitadas' not in st.session_state:
    st.session_state.visitadas = []

df = load_data()

# 2. Barra Lateral (Filtros)
st.sidebar.header("📍 Configuración de Ruta")
provincias = df['REGIONAL'].unique()
provincia_sel = st.sidebar.selectbox("Seleccionar Regional", provincias)

distritos = df[df['REGIONAL'] == provincia_sel]['DISTRITO'].unique()
distrito_sel = st.sidebar.selectbox("Seleccionar Distrito", distritos)

# Filtrar datos
subset = df[(df['REGIONAL'] == provincia_sel) & (df['DISTRITO'] == distrito_sel)].copy()

# Excluir las ya visitadas (El truco del Check)
subset = subset[~subset['CÓDIGO'].isin(st.session_state.visitadas)]

st.sidebar.markdown("---")
st.sidebar.metric("Escuelas Pendientes", len(subset))

# 3. Lógica de Optimización (Barrido + Vecino Cercano)
def optimizar_ruta(dataframe, group_size=5):
    if dataframe.empty: return []
    
    # Ordenar Oeste -> Este para agrupar
    df_sorted = dataframe.sort_values('LONGITUD')
    num_groups = int(np.ceil(len(df_sorted) / group_size))
    rutas = []
    
    for i in range(num_groups):
        chunk = df_sorted.iloc[i*group_size : (i+1)*group_size].copy()
        
        # Ordenar internamente (Vecino más cercano)
        if len(chunk) > 1:
            ordered = [chunk.index[0]] # Empezar con el primero del chunk
            remaining = [x for x in chunk.index if x != ordered[0]]
            
            while remaining:
                last_idx = ordered[-1]
                last_pt = chunk.loc[last_idx]
                # Encontrar el más cercano
                next_idx = min(remaining, key=lambda x: (chunk.loc[x, 'LATITUD'] - last_pt['LATITUD'])**2 + 
                                                        (chunk.loc[x, 'LONGITUD'] - last_pt['LONGITUD'])**2)
                ordered.append(next_idx)
                remaining.remove(next_idx)
            chunk = chunk.loc[ordered]
        
        chunk['Trayecto'] = i + 1
        rutas.append(chunk)
        
    return pd.concat(rutas) if rutas else pd.DataFrame()

# Ejecutar optimización
df_optimizado = optimizar_ruta(subset)

# 4. Interfaz Principal
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader(f"🗺️ Mapa de Rutas - {distrito_sel}")
    
    if not df_optimizado.empty:
        # Centrar mapa
        avg_lat = df_optimizado['LATITUD'].mean()
        avg_lon = df_optimizado['LONGITUD'].mean()
        m = folium.Map(location=[avg_lat, avg_lon], zoom_start=12)
        
        colors = ['blue', 'red', 'green', 'orange', 'purple', 'darkblue']
        
        # Dibujar cada trayecto
        for trayecto in df_optimizado['Trayecto'].unique():
            data_t = df_optimizado[df_optimizado['Trayecto'] == trayecto]
            color = colors[(trayecto-1) % len(colors)]
            
            # Línea
            points = data_t[['LATITUD', 'LONGITUD']].values.tolist()
            folium.PolyLine(points, color=color, weight=4, opacity=0.7).add_to(m)
            
            # Marcadores
            for i, (idx, row) in enumerate(data_t.iterrows()):
                folium.Marker(
                    [row['LATITUD'], row['LONGITUD']],
                    popup=row['ESCUELA'],
                    tooltip=f"{i+1}. {row['ESCUELA']}",
                    icon=folium.Icon(color=color, icon='info-sign')
                ).add_to(m)
                
        st_folium(m, width=800, height=500)
    else:
        st.info("¡Felicidades! No hay escuelas pendientes en esta zona.")

with col2:
    st.subheader("✅ Gestión de Visitas")
    st.write("Marca las escuelas conforme las visitas para quitarlas del mapa.")
    
    if not df_optimizado.empty:
        # Selector de Trayecto para no mostrar todo de golpe
        trayectos = sorted(df_optimizado['Trayecto'].unique())
        trayecto_ver = st.selectbox("Ver Trayecto:", trayectos)
        
        lista_trabajo = df_optimizado[df_optimizado['Trayecto'] == trayecto_ver]
        
        for idx, row in lista_trabajo.iterrows():
            # Checkbox para marcar como visitado
            # Usamos una key única combinando código y estado
            check = st.checkbox(f"{row['ESCUELA']}", key=f"chk_{row['CÓDIGO']}")
            
            if check:
                if row['CÓDIGO'] not in st.session_state.visitadas:
                    st.session_state.visitadas.append(row['CÓDIGO'])
                    st.rerun() # Recargar la página para actualizar mapa
    else:
        st.success("Zona completada.")

# Botón para resetear (para demo)
if st.sidebar.button("Resetear todo"):
    st.session_state.visitadas = []
    st.rerun()
