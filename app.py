import streamlit as st
import pandas as pd
import gspread
from google.oauth2 import service_account
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json

# Configuración de la página
st.set_page_config(
    page_title="Sistema de Hojas Múltiples",
    page_icon="📑",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Título de la aplicación
st.title("📑 Sistema de Navegación entre Hojas de Cálculo")

# URLs de las hojas de cálculo
SHEET_URLS = {
    "Mérida": "https://docs.google.com/spreadsheets/d/13tPaaJCX4o4HkxrRdPiuc5NDP3XhrJuvKdq83Eh7-KU/edit?gid=56875334#gid=56875334",
    "Tuxtla": "https://docs.google.com/spreadsheets/d/1Stux8hR4IlZ879gL7TRbz3uKzputDVwR362VINUr5Ho/edit?gid=1168578915#gid=1168578915"
}

# Configuración para acceso a Google Sheets
def setup_gspread():
    try:
        # Intenta cargar credenciales desde secrets de Streamlit
        creds_dict = st.secrets["gcp_service_account"]
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=[
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ])
        return gspread.authorize(creds)
    except:
        st.warning("""
        **Configuración necesaria:** 
        Para acceder a todas las hojas, necesitas configurar las credenciales de Google Service Account.
        
        1. Ve a Google Cloud Console y crea una Service Account
        2. Descarga el JSON de credenciales
        3. En Streamlit, ve a Settings → Secrets y agrega las credenciales
        """)
        return None

# Función para obtener todas las hojas de un spreadsheet
def get_all_sheets(spreadsheet_url, client):
    try:
        spreadsheet = client.open_by_url(spreadsheet_url)
        worksheets = spreadsheet.worksheets()
        return {f"{ws.title} (ID: {ws.id})": ws for ws in worksheets}
    except Exception as e:
        st.error(f"Error al acceder al spreadsheet: {e}")
        return None

# Función para obtener datos de una hoja específica
def get_sheet_data(worksheet):
    try:
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        return df
    except Exception as e:
        st.error(f"Error al obtener datos: {e}")
        return None

# Función alternativa usando pandas directamente (sin autenticación)
def get_sheet_data_fallback(spreadsheet_url, gid=None):
    try:
        # Convertir URL a formato CSV de exportación
        if 'gid=' in spreadsheet_url:
            base_url = spreadsheet_url.split('gid=')[0]
            gid = spreadsheet_url.split('gid=')[1]
            csv_url = f"{base_url}export?format=csv&gid={gid}"
        else:
            csv_url = spreadsheet_url.replace('/edit', '/export?format=csv')
        
        df = pd.read_csv(csv_url)
        return df
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        return None

# Selector de ubicación
st.sidebar.header("📍 Selecciona Ubicación")
ubicacion = st.sidebar.radio("Ubicación:", ["Mérida", "Tuxtla"], index=0)

# Intentar autenticar con Google Sheets
client = setup_gspread()

if client:
    # Obtener todas las hojas del spreadsheet seleccionado
    sheets_dict = get_all_sheets(SHEET_URLS[ubicacion], client)
    
    if sheets_dict:
        # Obtener nombres de hojas
        sheet_names = list(sheets_dict.keys())
        
        # Mostrar selector de hojas en sidebar
        st.sidebar.header("📋 Selecciona Hoja")
        selected_sheet_name = st.sidebar.selectbox(
            "Hoja:",
            sheet_names,
            index=len(sheet_names)-1  # Última hoja por defecto
        )
        
        # Obtener datos de la hoja seleccionada
        selected_sheet = sheets_dict[selected_sheet_name]
        df = get_sheet_data(selected_sheet)
        
        if df is not None:
            # Mostrar información de la hoja
            st.header(f"📊 Datos de {ubicacion} - Hoja: {selected_sheet.title}")
            st.info(f"📋 Total de registros: {len(df)} | 📄 Total de columnas: {len(df.columns)}")
            
            # Mostrar datos
            st.dataframe(df, use_container_width=True, height=600)
            
            # Mostrar estadísticas básicas
            with st.expander("📈 Estadísticas Descriptivas"):
                st.write(df.describe())
            
            # Opciones de descarga
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Descargar CSV",
                data=csv,
                file_name=f"{ubicacion}_{selected_sheet.title}.csv",
                mime="text/csv"
            )
    else:
        st.error("No se pudieron cargar las hojas. Verifica los permisos.")
else:
    # Modo fallback: usar acceso público a la hoja predeterminada
    st.warning("Modo de acceso básico. Mostrando última hoja disponible públicamente.")
    
    # Obtener datos de la hoja predeterminada
    df = get_sheet_data_fallback(SHEET_URLS[ubicacion])
    
    if df is not None:
        st.header(f"📊 Datos de {ubicacion} (Última Hoja Disponible)")
        st.info(f"📋 Total de registros: {len(df)} | 📄 Total de columnas: {len(df.columns)}")
        
        # Mostrar datos
        st.dataframe(df, use_container_width=True, height=600)
        
        # Mostrar estadísticas básicas
        with st.expander("📈 Estadísticas Descriptivas"):
            st.write(df.describe())
        
        # Opciones de descarga
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar CSV",
            data=csv,
            file_name=f"{ubicacion}_datos.csv",
            mime="text/csv"
        )

# Información adicional en el sidebar
st.sidebar.header("ℹ️ Información")
st.sidebar.info("""
**Instrucciones:**
1. Selecciona la ubicación (Mérida o Tuxtla)
2. Elige la hoja específica que deseas visualizar
3. Explora los datos en la vista principal
4. Descarga los datos si es necesario
""")

st.sidebar.header("🔗 Enlaces Directos")
for name, url in SHEET_URLS.items():
    st.sidebar.markdown(f"- [{name}]({url})")

# Pie de página
st.divider()
st.markdown(
    "<div style='text-align: center; color: gray;'>Sistema de navegación de hojas • "
    f"{datetime.now().strftime('%Y-%m-%d %H:%M')}</div>",
    unsafe_allow_html=True
)
