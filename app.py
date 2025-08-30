import streamlit as st
import pandas as pd
import gspread
from google.oauth2 import service_account
from datetime import datetime

# Configuración de la página
st.set_page_config(
    page_title="Sistema de Hojas Múltiples",
    page_icon="📑",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Título de la aplicación
st.title("📑 Sistema de Navegación entre Hojas de Cálculo")

# URLs de las hojas de cálculo (solo los IDs)
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
            return None
            
        # Cargar credenciales desde Streamlit Secrets
        creds_dict = dict(st.secrets["gcp_service_account"])
        
        # Asegurarse de que la private key tenga el formato correcto
        if 'private_key' in creds_dict:
            creds_dict['private_key'] = creds_dict['private_key'].replace('\\n', '\n')
        
        creds = service_account.Credentials.from_service_account_info(
            creds_dict,
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
        st.error(f"Error al obtener datos: {e}")
        return None

# Función alternativa usando acceso público
def get_public_sheet_data(spreadsheet_id, sheet_name="Sheet1"):
    try:
        # Intentar acceso público
        url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
        df = pd.read_csv(url)
        return df
    except:
        try:
            # Segundo intento con formato diferente
            url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv"
            df = pd.read_csv(url)
            return df
        except Exception as e:
            st.error(f"No se pudo acceder a los datos: {e}")
            return None

# Obtener cliente de Google Sheets
client = setup_gspread()

# Selector de ubicación en el sidebar
st.sidebar.header("📍 Selecciona Ubicación")
ubicacion = st.sidebar.radio("Ubicación:", ["Mérida", "Tuxtla"], index=0)

spreadsheet_id = SHEET_IDS[ubicacion]

if client:
    # Modo autenticado - acceso completo a todas las hojas
    with st.spinner("Cargando hojas disponibles..."):
        sheets_dict = get_all_sheets(spreadsheet_id, client)
    
    if sheets_dict:
        # Obtener nombres de hojas
        sheet_names = list(sheets_dict.keys())
        
        # Mostrar selector de hojas en sidebar
        st.sidebar.header("📋 Selecciona Hoja")
        selected_sheet_name = st.sidebar.selectbox(
            "Hoja:",
            sheet_names,
            index=len(sheet_names)-1 if sheet_names else 0
        )
        
        # Obtener datos de la hoja seleccionada
        with st.spinner(f"Cargando {selected_sheet_name}..."):
            selected_sheet = sheets_dict[selected_sheet_name]
            df = get_sheet_data(selected_sheet)
        
        if df is not None and not df.empty:
            # Mostrar información de la hoja
            st.header(f"📊 {ubicacion} - {selected_sheet_name}")
            
            # Métricas en la parte superior
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Registros", len(df))
            with col2:
                st.metric("Columnas", len(df.columns))
            with col3:
                numeric_cols = df.select_dtypes(include=['number']).columns
                st.metric("Columnas numéricas", len(numeric_cols))
            
            # Mostrar datos
            st.dataframe(df, use_container_width=True, height=400)
            
            # Estadísticas básicas
            if not numeric_cols.empty:
                with st.expander("📈 Estadísticas de columnas numéricas"):
                    st.dataframe(df[numeric_cols].describe())
            
            # Opciones de descarga
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Descargar CSV",
                data=csv,
                file_name=f"{ubicacion}_{selected_sheet_name}.csv".replace(" ", "_"),
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.warning("La hoja seleccionada está vacía o no se pudieron cargar los datos.")
    else:
        st.error("No se pudieron cargar las hojas. Verifica los permisos.")
else:
    # Modo público - intentar cargar la hoja principal
    st.warning("🔐 Usando acceso público. Algunas funciones pueden estar limitadas.")
    
    with st.spinner("Cargando datos..."):
        df = get_public_sheet_data(spreadsheet_id)
    
    if df is not None and not df.empty:
        st.header(f"📊 {ubicacion} - Hoja Principal")
        
        # Métricas
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Registros", len(df))
        with col2:
            st.metric("Columnas", len(df.columns))
        with col3:
            numeric_cols = df.select_dtypes(include=['number']).columns
            st.metric("Columnas numéricas", len(numeric_cols))
        
        # Mostrar datos
        st.dataframe(df, use_container_width=True, height=400)
        
        # Estadísticas
        if not numeric_cols.empty:
            with st.expander("📈 Estadísticas de columnas numéricas"):
                st.dataframe(df[numeric_cols].describe())
        
        # Descarga
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar CSV",
            data=csv,
            file_name=f"{ubicacion}_datos.csv",
            mime="text/csv",
            use_container_width=True
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
for name, sheet_id in SHEET_IDS.items():
    st.sidebar.markdown(f"- [{name}](https://docs.google.com/spreadsheets/d/{sheet_id}/)")

# Instrucciones para configurar secrets
with st.sidebar.expander("⚙️ Configurar Secrets"):
    st.markdown("""
    **Para acceso completo, configura en Streamlit Secrets:**
    
    ```toml
    [gcp_service_account]
    type = "service_account"
    project_id = "plasma-envoy-460522-r6"
    private_key_id = "9cbbb40ae6b09c92f7aeb65045179f359a68afc3"
    private_key = """
    -----BEGIN PRIVATE KEY-----
    MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDSm9Kkk2SEeDvR
    aSjgJ36oNE+PgUjt0zykk8SsMonnbUIG3l7eU/ohksJagQtV48DZtcixt0LtRjyT
    yTMLL17Cbd6w1aPwfDqudCp2XsQDH0YmDyVOWiaOhi8n8qkjEr4XduBe89mdLJ/G
    x0uTc6Bl4A8S7anx1qVIadK4ejcUr+6eFZc3IXZ5hym2D5Veu5NjrrDR3hXYchT+
    52xO4auXN+XEZPO+jrAA49YI5pjTb8s4yETuxG9n0QSYazPoPBzzWbQtc55SW+EG
    jdiabhAJpAlrTgbDX6YBjMbFC/ZleOMOypkUjEqffKqOii1FdfjEpdYaVJIVvdUU
    KlTXLEXfAgMBAAECggEAHxUTMz8eMcoYM0bnWvRJO47Y18TiBq4gauj0uOCOkg1X
    FhzBzeMr7ReJP9fVXJw2gor9xHNXrnKpZGWTIclLHWZ0sWQeWVLO9Z88WGg9BSRG
    SJNUqKnNEJzEyeBaI6HTqd0yrkt5KDqv6/jOx8Nj/pULnySx6k4I6lUqiG0Kba69
    XyF2+qZ3rO2ZHLFU8i4GCuuAYzFNJRzqsD5+sfJYOD5KOmAJUtgfv4OjAkmTpqIV
    DSWRmOOexa/9It0o9goTYnt1uZlJ0tsdfE5kVPN671wqwFt+8qCEG9D2NfcLrbZ/
    FRBh9Cs5thnOEdenk3/Sv9Kj9X2+XcUjI4a+3tj91QKBgQD2kRH080SqPQV1HvZF
    jOhut9d4rQiqBEH/SK+JnriPEQOAwnDIl0UGLX9WqDsN28BXUR9hYs8sud1qzkzb
    QJG0uEAqdcGw2aCELCCoMcDxGDCV1sGQ1It2YL7cMelHoeCIj0vzKHQ9DkvxNdZj
    9BxWbYXu93qRtZKbuLKkzF7Y7QKBgQDaqpJpM7x7HrpIkn/YD9Jeqvq1chaAMZBy
    GzSTARbE8dgZGSrzke6RZHTNEjaQ6axhzKMu2lPbLaEWg32PRktfWpQQj2OHJwla
    nmjrc5Kbj831kSC3QIAUJVgKrFWzJFs9l/yyF3O+pAIojREuCVoRlalxkmu5IO/6
    gEGbqfy8ewKBgQDOvU7oKz3s3COCU8a9BGwzwbRKvBNisxU/XwvIgaxQUTy1rtNw
    bd3zUxzNZVu2wAZjcGK2fmomH2Y3UumAgYBqnn822uvgRGnhyTpMrQMRZG4AhURi
    EsUpKe9+o97tMB8bgcN2C/qC40Tr6G9t+dX05fqCJ0G/gRZ/uXsY0T/J9QKBgDZv
    fjFYYtSXqrJEXjUwgyN0FyOyei2BqT7uzODHxZ5TwoNFA69NJgHl6zneDd13fqV+
    JyWTzopiypZrN4fCbSMYzoFs4M8VhbuccewjglzdqN04OtfD496gCVHm4xLMuzYT
    LyI6umK8O5lSvPMj+tsj0eHnHJAixfsrkKmq4LMfAoGAFN+DuKCsGkagJssegM3z
    P41w5lRCytN0xnAyTFdEN7V+8kOj8DDo5sQxC9VYGKDtNpMGio6ZrdgW0Hymd+YH
    3onqBtuHBptORbGabjiZjIRGMfg3K2WgB31rOvxvRNvORu/rPt5tuAY+6xMnoBR4
    KDGGEXG2xOOCfDWale2cNcs=
    -----END PRIVATE KEY-----
    """
    client_email = "alfredapi@plasma-envoy-460522-r6.iam.gserviceaccount.com"
    client_id = "107534087740882230268"
    auth_uri = "https://accounts.google.com/o/oauth2/auth"
    token_uri = "https://oauth2.googleapis.com/token"
    auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
    client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/alfredapi%40plasma-envoy-460522-r6.iam.gserviceaccount.com"
    universe_domain = "googleapis.com"
    ```
    
    **No olvides compartir los Google Sheets con:**
    `alfredapi@plasma-envoy-460522-r6.iam.gserviceaccount.com`
    """)

# Pie de página
st.divider()
st.markdown(
    "<div style='text-align: center; color: gray;'>Sistema de navegación de hojas • "
    f"{datetime.now().strftime('%Y-%m-%d %H:%M')}</div>",
    unsafe_allow_html=True
)
