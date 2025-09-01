import streamlit as st
import pandas as pd
import gspread
from google.oauth2 import service_account
from datetime import datetime
import numpy as np
import re

# Configuración de la página
st.set_page_config(
    page_title="Sistema de Análisis de Precios por Hotel",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Título de la aplicación
st.title("🏨 Sistema de Análisis de Precios por Hotel")

# IDs de las hojas de cálculo
SHEET_IDS = {
    "Mérida": "13tPaaJCX4o4HkxrRdPiuc5NDP3XhrJuvKdq83Eh7-KU",
    "Tuxtla": "1Stux8hR4IlZ879gL7TRbz3uKzputDVwR362VINUr5Ho"
}

# Configuración para acceso a Google Sheets usando Secrets
def setup_gspread():
    try:
        # Verificar que los secrets existen
        if 'gcp_service_account' not in st.secrets:
            st.error("No se encontraron las credenciales en los Secrets.")
            st.info("Por favor configura las credenciales en Streamlit Secrets")
            return None
            
        # Cargar credenciales desde Streamlit Secrets
        creds_info = {
            "type": st.secrets["gcp_service_account"]["type"],
            "project_id": st.secrets["gcp_service_account"]["project_id"],
            "private_key_id": st.secrets["gcp_service_account"]["private_key_id"],
            "private_key": st.secrets["gcp_service_account"]["private_key"].replace('\\n', '\n'),
            "client_email": st.secrets["gcp_service_account"]["client_email"],
            "client_id": st.secrets["gcp_service_account"]["client_id"],
            "auth_uri": st.secrets["gcp_service_account"]["auth_uri"],
            "token_uri": st.secrets["gcp_service_account"]["token_uri"],
            "auth_provider_x509_cert_url": st.secrets["gcp_service_account"]["auth_provider_x509_cert_url"],
            "client_x509_cert_url": st.secrets["gcp_service_account"]["client_x509_cert_url"],
            "universe_domain": st.secrets["gcp_service_account"]["universe_domain"]
        }
        
        creds = service_account.Credentials.from_service_account_info(
            creds_info,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Error de autenticación: {e}")
        return None

# Función para obtener todas las hojas de un spreadsheet
def get_all_sheets(spreadsheet_id, client):
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheets = spreadsheet.worksheets()
        # Ordenar hojas por título (asumiendo que títulos tienen fechas)
        worksheets.sort(key=lambda x: x.title, reverse=True)
        return {f"{ws.title}": ws for ws in worksheets}
    except Exception as e:
        st.error(f"Error al acceder al spreadsheet: {e}")
        return None

# Función para obtener datos de una hoja específica
def get_sheet_data(worksheet):
    try:
        data = worksheet.get_all_records()
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        return df
    except Exception as e:
        st.error(f"Error al obtener datos de {worksheet.title}: {e}")
        return None

# Función para detectar automáticamente columnas relevantes
def detect_columns(df):
    # Buscar columna de hotel
    hotel_keywords = ['hotel', 'nombre', 'name', 'propiedad', 'establecimiento']
    price_keywords = ['precio', 'price', 'costo', 'cost', 'valor', 'value', 'monto', 'amount', 'importe']
    
    hotel_col = None
    price_col = None
    
    for col in df.columns:
        col_lower = str(col).lower()
        
        # Buscar columna de hotel
        if not hotel_col and any(keyword in col_lower for keyword in hotel_keywords):
            hotel_col = col
        
        # Buscar columna de precio
        if not price_col and any(keyword in col_lower for keyword in price_keywords):
            # Verificar si contiene valores numéricos
            try:
                numeric_test = pd.to_numeric(df[col].astype(str).str.replace(',', '.').str.replace('$', '').str.replace(' ', ''), errors='coerce')
                if numeric_test.notna().sum() > 0:
                    price_col = col
            except:
                continue
    
    # Si no se encuentra por nombre, intentar detectar
    if not hotel_col:
        for col in df.columns:
            # Buscar columnas con texto que podrían ser nombres
            if df[col].astype(str).str.len().mean() > 3 and df[col].astype(str).str.isnumeric().mean() < 0.5:
                hotel_col = col
                break
    
    if not price_col:
        # Buscar cualquier columna numérica
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            price_col = numeric_cols[0]
        else:
            # Intentar convertir columnas
            for col in df.columns:
                try:
                    numeric_series = pd.to_numeric(df[col].astype(str).str.replace(',', '.').str.replace('$', '').str.replace(' ', ''), errors='coerce')
                    if numeric_series.notna().sum() > 0:
                        price_col = col
                        break
                except:
                    continue
    
    return hotel_col, price_col

# Función para buscar hotel en múltiples hojas
def search_hotel_prices(client, spreadsheet_id, hotel_name, max_sheets=30):
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheets = spreadsheet.worksheets()
        # Ordenar hojas por título (más recientes primero)
        worksheets.sort(key=lambda x: x.title, reverse=True)
        
        resultados = []
        sheets_procesadas = 0
        precios_encontrados = 0
        
        for worksheet in worksheets:
            if sheets_procesadas >= max_sheets or precios_encontrados >= 30:
                break
                
            try:
                df = get_sheet_data(worksheet)
                if df is None or df.empty:
                    continue
                
                hotel_col, price_col = detect_columns(df)
                
                if hotel_col and price_col:
                    # Buscar el hotel (búsqueda insensible a mayúsculas)
                    mask = df[hotel_col].astype(str).str.lower().str.contains(hotel_name.lower(), na=False)
                    hotel_data = df[mask]
                    
                    if not hotel_data.empty:
                        # Procesar precios
                        for _, row in hotel_data.iterrows():
                            try:
                                precio = pd.to_numeric(
                                    str(row[price_col]).replace(',', '.').replace('$', '').replace(' ', ''),
                                    errors='coerce'
                                )
                                
                                if not pd.isna(precio) and precio > 0:
                                    resultados.append({
                                        'hoja': worksheet.title,
                                        'hotel': row[hotel_col],
                                        'precio': precio,
                                        'fecha_hoja': worksheet.title  # Asumimos que el título contiene la fecha
                                    })
                                    precios_encontrados += 1
                                    
                                    if precios_encontrados >= 30:
                                        break
                            except:
                                continue
                
                sheets_procesadas += 1
                
            except Exception as e:
                st.warning(f"Error procesando hoja {worksheet.title}: {e}")
                continue
        
        return pd.DataFrame(resultados)
    
    except Exception as e:
        st.error(f"Error en la búsqueda: {e}")
        return pd.DataFrame()

# Función para calcular métricas de los precios encontrados
def calculate_hotel_metrics(resultados_df):
    if resultados_df.empty:
        return None
    
    precios = resultados_df['precio']
    
    return {
        'total_hojas_revisadas': resultados_df['hoja'].nunique(),
        'total_precios_encontrados': len(precios),
        'precio_minimo': precios.min(),
        'precio_maximo': precios.max(),
        'suma_total': precios.sum(),
        'promedio': precios.mean(),
        'precio_mediano': precios.median(),
        'desviacion_estandar': precios.std()
    }

# Selector de ubicación en el sidebar
st.sidebar.header("📍 Selecciona Ubicación")
ubicacion = st.sidebar.radio("Ubicación:", ["Mérida", "Tuxtla"], index=0)

spreadsheet_id = SHEET_IDS[ubicacion]

# Obtener cliente de Google Sheets
client = setup_gspread()

# Barra de búsqueda de hotel
st.header("🔍 Búsqueda de Precios por Hotel")
hotel_busqueda = st.text_input(
    "Ingresa el nombre del hotel a buscar:",
    placeholder="Ej: Hotel Continental, Hilton, etc..."
)

if hotel_busqueda.strip():
    if client:
        with st.spinner(f"Buscando '{hotel_busqueda}' en las últimas 30 hojas..."):
            resultados = search_hotel_prices(client, spreadsheet_id, hotel_busqueda, max_sheets=30)
        
        if not resultados.empty:
            st.success(f"✅ Se encontraron {len(resultados)} precios para hoteles que coinciden con '{hotel_busqueda}'")
            
            # Calcular métricas
            metrics = calculate_hotel_metrics(resultados)
            
            # Mostrar métricas
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Precios encontrados", metrics['total_precios_encontrados'])
            
            with col2:
                st.metric("Precio Mínimo", f"${metrics['precio_minimo']:,.2f}")
            
            with col3:
                st.metric("Precio Máximo", f"${metrics['precio_maximo']:,.2f}")
            
            with col4:
                st.metric("Suma Total", f"${metrics['suma_total']:,.2f}")
            
            # Promedio y detalles
            col5, col6 = st.columns(2)
            
            with col5:
                st.metric("Promedio", f"${metrics['promedio']:,.2f}")
            
            with col6:
                st.metric("Hojas revisadas", metrics['total_hojas_revisadas'])
            
            # Detalles del cálculo
            with st.expander("📊 Detalles completos del análisis"):
                st.write(f"**Fórmula del promedio:** Suma total / Cantidad de precios")
                st.write(f"**Suma total:** ${metrics['suma_total']:,.2f}")
                st.write(f"**Cantidad de precios:** {metrics['total_precios_encontrados']}")
                st.write(f"**Cálculo:** ${metrics['suma_total']:,.2f} / {metrics['total_precios_encontrados']} = ${metrics['promedio']:,.2f}")
                st.write(f"**Precio mediano:** ${metrics['precio_mediano']:,.2f}")
                st.write(f"**Desviación estándar:** ${metrics['desviacion_estandar']:,.2f}")
            
            # Mostrar resultados detallados
            st.subheader("📋 Precios Encontrados")
            st.dataframe(
                resultados.sort_values('precio', ascending=False),
                use_container_width=True,
                height=300
            )
            
            # Gráfico de precios
            st.subheader("📈 Distribución de Precios")
            st.bar_chart(resultados.set_index('hotel')['precio'])
            
            # Opción para descargar resultados
            csv = resultados.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Descargar Resultados de Búsqueda",
                data=csv,
                file_name=f"precios_{hotel_busqueda.lower().replace(' ', '_')}.csv",
                mime="text/csv"
            )
            
        else:
            st.warning(f"❌ No se encontraron precios para hoteles que coincidan con '{hotel_busqueda}'")
            st.info("""
            **Sugerencias:**
            - Verifica la ortografía del nombre del hotel
            - Intenta con un término de búsqueda más general
            - Asegúrate de que el hotel exista en los datos de {ubicacion}
            """)
    else:
        st.error("❌ No se pudo conectar con Google Sheets. Verifica la configuración.")

# Información adicional
st.sidebar.header("ℹ️ Información de Búsqueda")
st.sidebar.info("""
**Cómo funciona la búsqueda:**
1. Busca en las últimas 30 hojas
2. Encuentra coincidencias parciales del nombre
3. Suma todos los precios encontrados
4. Calcula el promedio entre todas las hojas
5. Muestra análisis completo
""")

st.sidebar.header("🔗 Enlaces Directos")
for name, sheet_id in SHEET_IDS.items():
    st.sidebar.markdown(f"- [{name}](https://docs.google.com/spreadsheets/d/{sheet_id}/)")

# Pie de página
st.divider()
st.markdown(
    "<div style='text-align: center; color: gray;'>Sistema de análisis de precios por hotel • "
    f"{datetime.now().strftime('%Y-%m-%d %H:%M')}</div>",
    unsafe_allow_html=True
)
