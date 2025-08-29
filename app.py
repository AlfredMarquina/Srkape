import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import time
import pandas as pd
import numpy as np
import os

# SOLUCIÓN: Deshabilitar el watcher de páginas para evitar el error
os.environ["STREAMLIT_SERVER_ENABLE_STATIC_FILE_WATCHING"] = "false"

# =============================================================================
# CONFIGURACIÓN COMPLETA DE LA APLICACIÓN
# =============================================================================
st.set_page_config(
    page_title="Sistema de Análisis Mérida",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://docs.streamlit.io/',
        'Report a bug': 'https://github.com/streamlit/streamlit/issues',
        'About': '''
        ## 📊 Sistema de Análisis de Precios Mérida
        **Versión:** 1.0
        **Función:** Calcula el promedio de promedios de las últimas 30 hojas
        '''
    }
)

# Configuración adicional para prevenir errores
st.markdown("""
<style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    .stButton button {
        background-color: #FF4B4B;
        color: white;
    }
    .stButton button:hover {
        background-color: #FF6B6B;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# TÍTULO Y DESCRIPCIÓN DE LA APLICACIÓN
# =============================================================================
st.title("📊 Sistema de Análisis de Precios Mérida")
st.markdown("---")

# =============================================================================
# SIDEBAR CON CONFIGURACIÓN
# =============================================================================
with st.sidebar:
    st.header("⚙️ Configuración")
    st.markdown("---")
    
    # Inputs para los IDs de Google Sheets
    SPREADSHEET_ID_ORIGEN = st.text_input(
        "📋 ID Spreadsheet Origen",
        value="1TZo6pSlhoFFf00ruIv2dpjszHUMK4I9T_ZFQdo50jEk",
        help="ID del Google Sheet donde están tus datos diarios"
    )
    
    SPREADSHEET_ID_DESTINO = st.text_input(
        "💾 ID Spreadsheet Destino", 
        value="1DgZ7I5kRxOPXE0iQGfqalbkmaOLubBCFipAs7zWqb2g",
        help="ID del Google Sheet donde se guardarán los resultados"
    )
    
    st.markdown("---")
    
    # Selector de funcionalidad
    funcion = st.selectbox(
        "Selecciona la operación:",
        ["Calcular Promedio de Promedios", "Solo Mostrar Datos"]
    )
    
    st.markdown("---")
    
    # Botón de ejecución
    ejecutar = st.button("🚀 Ejecutar Análisis", type="primary", use_container_width=True)
    
    st.markdown("---")
    st.info("💡 Asegúrate de que las hojas tengan datos y el formato correcto")

# =============================================================================
# FUNCIONES PRINCIPALES
# =============================================================================
def authenticate_google_sheets():
    """Autenticación con Google Sheets API usando Streamlit Secrets"""
    try:
        SCOPES = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # Obtener credenciales desde Streamlit Secrets
        if 'google_credentials' not in st.secrets:
            st.error("❌ No se encontraron credenciales en Secrets. Por favor configura las credenciales en la sección de Secrets de Streamlit.")
            return None, False
            
        creds_dict = dict(st.secrets["google_credentials"])
        
        credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        client = gspread.authorize(credentials)
        return client, True
    except Exception as e:
        st.error(f"❌ Error en autenticación: {str(e)}")
        return None, False

def extract_promedio_final(worksheet):
    """Extraer el valor del promedio final de una hoja"""
    try:
        data = worksheet.get_all_values()
        
        if len(data) <= 1:
            return None
        
        # Buscar específicamente "Promedio:" en los datos
        for row_idx, row in enumerate(data):
            for col_idx, cell in enumerate(row):
                if cell and 'promedio:' in cell.lower():
                    # Buscar valor en la celda siguiente
                    if col_idx + 1 < len(row):
                        valor_cell = row[col_idx + 1]
                        if valor_cell and '$' in valor_cell:
                            try:
                                # Limpiar y convertir el valor
                                valor_limpio = valor_cell.replace('$', '').replace('MXN', '')
                                valor_limpio = valor_limpio.replace('mxn', '').replace('MX', '')
                                valor_limpio = valor_limpio.replace(',', '').strip()
                                
                                if valor_limpio and valor_limpio.replace('.', '', 1).isdigit():
                                    promedio = float(valor_limpio)
                                    # Filtrar valores razonables para promedios
                                    if 100000 <= promedio <= 1000000:
                                        return promedio
                            except ValueError:
                                continue
        return None
    except Exception as e:
        st.error(f"Error procesando hoja: {str(e)}")
        return None

def calculate_promedio_de_promedios(client, spreadsheet_id_origen):
    """Calcular el promedio de los promedios finales"""
    try:
        spreadsheet_origen = client.open_by_key(spreadsheet_id_origen)
        all_worksheets = spreadsheet_origen.worksheets()
        ultimas_hojas = all_worksheets[-30:] if len(all_worksheets) >= 30 else all_worksheets
        
        st.info(f"📑 Analizando {len(ultimas_hojas)} hojas...")
        
        promedios_finales = []
        hojas_procesadas = []
        
        # Barra de progreso
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, worksheet in enumerate(ultimas_hojas):
            status_text.text(f"Procesando hoja {i+1}/{len(ultimas_hojas)}: {worksheet.title}")
            progress_bar.progress((i + 1) / len(ultimas_hojas))
            
            promedio = extract_promedio_final(worksheet)
            if promedio is not None:
                promedios_finales.append(promedio)
                hojas_procesadas.append(worksheet.title)
                st.sidebar.success(f"✅ {worksheet.title}: ${promedio:,.2f}")
            else:
                st.sidebar.warning(f"⚠️ {worksheet.title}: Sin promedio")
            
            time.sleep(0.1)
        
        # Limpiar barra de progreso
        progress_bar.empty()
        status_text.empty()
        
        if not promedios_finales:
            st.error("❌ No se encontraron promedios en ninguna hoja")
            return None
        
        # Calcular estadísticas
        promedio_final = sum(promedios_finales) / len(promedios_finales)
        
        return {
            'promedio_de_promedios': promedio_final,
            'minimo': min(promedios_finales),
            'maximo': max(promedios_finales),
            'total_hojas': len(ultimas_hojas),
            'hojas_con_promedio': len(promedios_finales),
            'promedios_individuales': promedios_finales,
            'nombres_hojas': hojas_procesadas,
            'fecha_calculo': datetime.now()
        }
        
    except Exception as e:
        st.error(f"❌ Error en cálculo: {str(e)}")
        return None

def save_results_to_sheet(client, spreadsheet_id_destino, results):
    """Guardar resultados en el spreadsheet destino"""
    try:
        spreadsheet_destino = client.open_by_key(spreadsheet_id_destino)
        worksheet = spreadsheet_destino.sheet1
        
        # Preparar datos
        fecha_str = results['fecha_calculo'].strftime('%Y-%m-%d %H:%M:%S')
        datos = [
            fecha_str,
            results['promedio_de_promedios'],
            results['minimo'],
            results['maximo'],
            results['total_hojas'],
            results['hojas_con_promedio']
        ]
        
        # Obtener datos existentes
        existing_data = worksheet.get_all_values()
        
        if not existing_data:
            # Crear encabezados si la hoja está vacía
            encabezados = [
                "Fecha", 
                "Promedio de Promedios (MXN)", 
                "Mínimo", 
                "Máximo",
                "Total Hojas",
                "Hojas con Promedio"
            ]
            worksheet.update([encabezados, datos])
        else:
            # Agregar nueva fila
            worksheet.append_row(datos)
        
        return True
        
    except Exception as e:
        st.error(f"❌ Error al guardar resultados: {str(e)}")
        return False

# =============================================================================
# LÓGICA PRINCIPAL DE LA APLICACIÓN
# =============================================================================
def main():
    if ejecutar:
        if not SPREADSHEET_ID_ORIGEN or not SPREADSHEET_ID_DESTINO:
            st.error("❌ Por favor ingresa ambos IDs de Google Sheets")
            return
        
        # Autenticación
        client, success = authenticate_google_sheets()
        if not success:
            return
        
        # Ejecutar según la opción seleccionada
        if funcion == "Calcular Promedio de Promedios":
            with st.spinner("🔄 Calculando promedios..."):
                resultados = calculate_promedio_de_promedios(client, SPREADSHEET_ID_ORIGEN)
                
                if resultados:
                    # Mostrar resultados
                    st.success("✅ ¡Cálculo completado exitosamente!")
                    st.balloons()
                    
                    # Métricas principales
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric(
                            "📊 Promedio de Promedios", 
                            f"${resultados['promedio_de_promedios']:,.2f} MXN",
                            delta=f"{resultados['promedio_de_promedios']/1000:,.1f}K"
                        )
                    with col2:
                        st.metric(
                            "📉 Mínimo", 
                            f"${resultados['minimo']:,.2f} MXN"
                        )
                    with col3:
                        st.metric(
                            "📈 Máximo", 
                            f"${resultados['maximo']:,.2f} MXN"
                        )
                    
                    # Estadísticas adicionales
                    col4, col5 = st.columns(2)
                    with col4:
                        st.info(f"📋 Total de hojas analizadas: {resultados['total_hojas']}")
                    with col5:
                        st.info(f"✅ Hojas con promedio encontrado: {resultados['hojas_con_promedio']}")
                    
                    # Guardar resultados
                    with st.spinner("💾 Guardando resultados..."):
                        if save_results_to_sheet(client, SPREADSHEET_ID_DESTINO, resultados):
                            st.success("✅ Resultados guardados en Google Sheets")
                    
                    # Mostrar algunos promedios individuales
                    with st.expander("📋 Ver promedios individuales"):
                        for i, (nombre, promedio) in enumerate(zip(resultados['nombres_hojas'], resultados['promedios_individuales'])):
                            if i < 10:  # Mostrar solo los primeros 10
                                st.write(f"**{nombre}**: ${promedio:,.2f} MXN")
                        
                        if len(resultados['promedios_individuales']) > 10:
                            st.info(f"... y {len(resultados['promedios_individuales']) - 10} más")
        
        elif funcion == "Solo Mostrar Datos":
            try:
                spreadsheet = client.open_by_key(SPREADSHEET_ID_ORIGEN)
                hojas = spreadsheet.worksheets()
                st.success(f"✅ Conectado a {spreadsheet.title}")
                st.info(f"📑 Número de hojas: {len(hojas)}")
                
                # Mostrar nombres de las últimas 10 hojas
                with st.expander("📋 Ver nombres de hojas"):
                    for i, hoja in enumerate(hojas[-10:]):
                        st.write(f"{i+1}. {hoja.title}")
                
            except Exception as e:
                st.error(f"❌ Error al conectar: {str(e)}")
    
    else:
        # PANTALLA DE INICIO
        st.markdown("""
        ## 🎯 Bienvenido al Sistema de Análisis de Precios Mérida
        
        ### 📋 ¿Qué hace esta aplicación?
        
        - ✅ **Calcula automáticamente** el promedio de promedios de las últimas 30 hojas
        - ✅ **Extrae los valores** de "Promedio:" de cada hoja de cálculo
        - ✅ **Guarda los resultados** en tu Google Sheet destino
        - ✅ **Muestra métricas** en tiempo real con gráficos
        
        ### 🚀 ¿Cómo usar?
        
        1. **Configura los IDs** de tus Google Sheets en el sidebar ←
        2. **Selecciona** la operación deseada
        3. **Haz clic** en "Ejecutar Análisis"
        4. **Espera** a que se procesen las hojas
        5. **Revisa** los resultados en esta pantalla
        
        ### 📊 IDs de Google Sheets:
        
        - **📋 Origen**: Donde están tus datos diarios (hojas por fecha)
        - **💾 Destino**: Donde se guardarán los resultados del cálculo
        
        ### ⚠️ Requisitos:
        
        - Credenciales de Google API configuradas en Streamlit Secrets
        - Permisos de lectura en el spreadsheet origen
        - Permisos de escritura en el spreadsheet destino
        - Conexión a internet estable
        """)
        
        # Información sobre cómo configurar Secrets
        with st.expander("🔐 Configuración de Secrets en Streamlit"):
            st.markdown("""
            ### Cómo configurar las credenciales de Google API:
            
            1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
            2. Crea un proyecto o selecciona uno existente
            3. Habilita **Google Sheets API** y **Google Drive API**
            4. Ve a "Credenciales" → "Crear credenciales" → "Cuenta de servicio"
            5. Descarga el archivo JSON de la cuenta de servicio
            6. En Streamlit Cloud, ve a la configuración de tu app
            7. En la pestaña "Secrets", pega el contenido del JSON con el formato:
            
            ```toml
            [google_credentials]
            type = "service_account"
            project_id = "tu-project-id"
            private_key_id = "tu-private-key-id"
            private_key = "-----BEGIN PRIVATE KEY-----\\ntu-clave-privada-completa-aqui\\n-----END PRIVATE KEY-----\\n"
            client_email = "tu-email@tu-proyecto.iam.gserviceaccount.com"
            client_id = "tu-client-id"
            auth_uri = "https://accounts.google.com/o/oauth2/auth"
            token_uri = "https://oauth2.googleapis.com/token"
            auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
            client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/tu-email%40tu-proyecto.iam.gserviceaccount.com"
            ```
            """)

# =============================================================================
# EJECUCIÓN DE LA APLICACIÓN
# =============================================================================
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"❌ Error inesperado: {str(e)}")
        st.info("🔄 Por favor recarga la página (Ctrl + F5)")

# =============================================================================
# FOOTER
# =============================================================================
st.markdown("---")
st.caption(f"📅 Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.caption("⚡ Powered by Streamlit + Google Sheets API")
