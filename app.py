import streamlit as st
import pandas as pd
import gspread
from google.oauth2 import service_account
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
    "Mérida": "13tPaaJCX4o4HkxrRdPiuc5NDP3XhrJuvKdq83Eh7-KU",
    "Tuxtla": "1Stux8hR4IlZ879gL7TRbz3uKzputDVwR362VINUr5Ho"
}

# Configuración para acceso a Google Sheets usando Secrets
def setup_gspread():
    try:
        # Cargar credenciales desde Streamlit Secrets
        creds_dict = st.secrets["gcp_service_account"]
        creds = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=[
                "https://spreadsheets.google.com/feeds",
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
        return {f"{ws.title}": ws for ws in worksheets}
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

# Función alternativa usando acceso público
def get_public_sheet_data(spreadsheet_id, sheet_name=None):
    try:
        if sheet_name:
            url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
        else:
            url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv"
        
        df = pd.read_csv(url)
        return df
    except Exception as e:
        st.error(f"Error al cargar datos públicos: {e}")
        return None

# Obtener cliente de Google Sheets
client = setup_gspread()

# Selector de ubicación en el sidebar
st.sidebar.header("📍 Selecciona Ubicación")
ubicacion = st.sidebar.radio("Ubicación:", ["Mérida", "Tuxtla"], index=0)

spreadsheet_id = SHEET_URLS[ubicacion]

if client:
    # Modo autenticado - acceso completo a todas las hojas
    sheets_dict = get_all_sheets(spreadsheet_id, client)
    
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
        
        if df is not None and not df.empty:
            # Mostrar información de la hoja
            st.header(f"📊 {ubicacion} - {selected_sheet_name}")
            st.info(f"📋 Registros: {len(df)} | 📄 Columnas: {len(df.columns)}")
            
            # Mostrar datos
            st.dataframe(df, use_container_width=True, height=500)
            
            # Estadísticas básicas
            with st.expander("📈 Estadísticas Descriptivas"):
                numeric_cols = df.select_dtypes(include=['number']).columns
                if len(numeric_cols) > 0:
                    st.write(df[numeric_cols].describe())
                else:
                    st.write("No hay columnas numéricas para mostrar estadísticas.")
            
            # Opciones de descarga
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Descargar CSV",
                data=csv,
                file_name=f"{ubicacion}_{selected_sheet_name}.csv",
                mime="text/csv"
            )
        else:
            st.warning("La hoja seleccionada está vacía o no se pudieron cargar los datos.")
    else:
        st.error("No se pudieron cargar las hojas. Verifica los permisos.")
else:
    # Modo público - intentar cargar la última hoja
    st.warning("🔐 Modo de acceso básico. Usando acceso público.")
    
    # Intentar cargar datos de forma pública
    df = get_public_sheet_data(spreadsheet_id)
    
    if df is not None and not df.empty:
        st.header(f"📊 {ubicacion} - Última Hoja Disponible")
        st.info(f"📋 Registros: {len(df)} | 📄 Columnas: {len(df.columns)}")
        
        # Mostrar datos
        st.dataframe(df, use_container_width=True, height=500)
        
        # Estadísticas básicas
        with st.expander("📈 Estadísticas Descriptivas"):
            numeric_cols = df.select_dtypes(include=['number']).columns
            if len(numeric_cols) > 0:
                st.write(df[numeric_cols].describe())
            else:
                st.write("No hay columnas numéricas para mostrar estadísticas.")
        
        # Opciones de descarga
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar CSV",
            data=csv,
            file_name=f"{ubicacion}_datos.csv",
            mime="text/csv"
        )
    else:
        st.error("No se pudieron cargar los datos. Verifica que la hoja sea pública.")

# Información adicional en el sidebar
st.sidebar.header("ℹ️ Información")
st.sidebar.info("""
**Instrucciones:**
1. Selecciona la ubicación
2. Elige la hoja específica
3. Explora los datos
4. Descarga si es necesario
""")

st.sidebar.header("🔗 Enlaces Directos")
for name, sheet_id in SHEET_URLS.items():
    st.sidebar.markdown(f"- [{name}](https://docs.google.com/spreadsheets/d/{sheet_id}/)")

# Pie de página
st.divider()
st.markdown(
    "<div style='text-align: center; color: gray;'>Sistema de navegación de hojas • "
    f"{datetime.now().strftime('%Y-%m-%d %H:%M')}</div>",
    unsafe_allow_html=True
)
