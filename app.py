import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import time
import pandas as pd

# Configuración de la página
st.set_page_config(
    page_title="Sistema de Análisis Mérida",
    page_icon="📊",
    layout="wide"
)

# Título de la aplicación
st.title("📊 Sistema de Análisis de Precios Mérida")
st.markdown("---")

# Sidebar con configuración
with st.sidebar:
    st.header("⚙️ Configuración")
    
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
    st.info("💡 Asegúrate de que el archivo 'credentials.json' esté en la raíz del proyecto")

# Clase para el cálculo de promedios
class PromedioPromediosCalculator:
    def __init__(self, spreadsheet_id_origen, spreadsheet_id_destino, credentials_file):
        self.SPREADSHEET_ID_ORIGEN = spreadsheet_id_origen
        self.SPREADSHEET_ID_DESTINO = spreadsheet_id_destino
        self.CREDENTIALS_FILE = credentials_file
        self.SCOPES = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        self.client = None
        self.spreadsheet_origen = None
        self.spreadsheet_destino = None
        
    def authenticate(self):
        try:
            credentials = Credentials.from_service_account_file(
                self.CREDENTIALS_FILE, scopes=self.SCOPES
            )
            self.client = gspread.authorize(credentials)
            return True
        except Exception as e:
            st.error(f"❌ Error en autenticación: {e}")
            return False
    
    def connect_to_spreadsheets(self):
        try:
            self.spreadsheet_origen = self.client.open_by_key(self.SPREADSHEET_ID_ORIGEN)
            self.spreadsheet_destino = self.client.open_by_key(self.SPREADSHEET_ID_DESTINO)
            return True
        except Exception as e:
            st.error(f"❌ Error al conectar: {e}")
            return False
    
    def extract_promedio_final(self, worksheet):
        try:
            data = worksheet.get_all_values()
            
            if len(data) <= 1:
                return None
            
            # Buscar específicamente "Promedio:"
            for row_idx, row in enumerate(data):
                for col_idx, cell in enumerate(row):
                    if cell and 'promedio:' in cell.lower():
                        if col_idx + 1 < len(row):
                            valor_cell = row[col_idx + 1]
                            if valor_cell and '$' in valor_cell:
                                try:
                                    valor_limpio = valor_cell.replace('$', '').replace('MXN', '')
                                    valor_limpio = valor_limpio.replace('mxn', '').replace('MX', '')
                                    valor_limpio = valor_limpio.replace(',', '').strip()
                                    
                                    if valor_limpio and valor_limpio.replace('.', '', 1).isdigit():
                                        return float(valor_limpio)
                                except ValueError:
                                    continue
            return None
            
        except Exception as e:
            st.error(f"Error procesando {worksheet.title}: {e}")
            return None
    
    def calculate_promedio_de_promedios(self):
        all_worksheets = self.spreadsheet_origen.worksheets()
        ultimas_hojas = all_worksheets[-30:] if len(all_worksheets) >= 30 else all_worksheets
        
        promedios_finales = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, worksheet in enumerate(ultimas_hojas):
            status_text.text(f"📋 Procesando hoja {i+1}/{len(ultimas_hojas)}: {worksheet.title}")
            progress_bar.progress((i + 1) / len(ultimas_hojas))
            
            promedio = self.extract_promedio_final(worksheet)
            if promedio is not None:
                promedios_finales.append(promedio)
            
            time.sleep(0.1)
        
        progress_bar.empty()
        status_text.empty()
        
        if not promedios_finales:
            return None
        
        return {
            'promedio_de_promedios': sum(promedios_finales) / len(promedios_finales),
            'minimo': min(promedios_finales),
            'maximo': max(promedios_finales),
            'total_promedios': len(promedios_finales),
            'fecha_calculo': datetime.now()
        }
    
    def save_results(self, results):
        try:
            worksheet = self.spreadsheet_destino.sheet1
            
            fecha_str = results['fecha_calculo'].strftime('%Y-%m-%d %H:%M:%S')
            datos = [
                fecha_str,
                results['promedio_de_promedios'],
                results['minimo'],
                results['maximo']
            ]
            
            existing_data = worksheet.get_all_values()
            
            if not existing_data:
                encabezados = ["Fecha", "Promedio de Promedios (MXN)", "Mínimo", "Máximo"]
                worksheet.update(values=[encabezados, datos])
            else:
                next_row = len(existing_data) + 1
                worksheet.update(values=[datos], range_name=f'A{next_row}')
            
            return True
            
        except Exception as e:
            st.error(f"❌ Error al guardar: {e}")
            return False

# Botón de ejecución en el sidebar
with st.sidebar:
    st.markdown("---")
    ejecutar = st.button("🚀 Ejecutar Cálculo de Promedios", type="primary")

# Main content
if ejecutar:
    if not SPREADSHEET_ID_ORIGEN or not SPREADSHEET_ID_DESTINO:
        st.error("❌ Por favor ingresa ambos IDs de Google Sheets")
    else:
        # Mostrar información de ejecución
        st.info("🔄 Iniciando cálculo de promedios...")
        
        # Crear instancia y ejecutar
        calculator = PromedioPromediosCalculator(
            SPREADSHEET_ID_ORIGEN,
            SPREADSHEET_ID_DESTINO,
            "credentials.json"
        )
        
        if calculator.authenticate() and calculator.connect_to_spreadsheets():
            resultados = calculator.calculate_promedio_de_promedios()
            
            if resultados:
                # Mostrar resultados
                st.success("✅ Cálculo completado exitosamente!")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("📊 Promedio de Promedios", f"${resultados['promedio_de_promedios']:,.2f} MXN")
                with col2:
                    st.metric("📉 Mínimo", f"${resultados['minimo']:,.2f} MXN")
                with col3:
                    st.metric("📈 Máximo", f"${resultados['maximo']:,.2f} MXN")
                
                # Guardar resultados
                if calculator.save_results(resultados):
                    st.success("💾 Resultados guardados en Google Sheets")
                else:
                    st.error("❌ Error al guardar resultados")
            else:
                st.error("❌ No se encontraron promedios para calcular")
        else:
            st.error("❌ Error de conexión con Google Sheets")

else:
    # Pantalla de inicio
    st.markdown("""
    ## 🎯 Bienvenido al Sistema de Análisis de Precios
    
    ### 📋 ¿Qué hace esta aplicación?
    
    - ✅ **Calcula automáticamente** el promedio de promedios de las últimas 30 hojas
    - ✅ **Extrae los valores** de "Promedio:" de cada hoja de cálculo
    - ✅ **Guarda los resultados** en tu Google Sheet destino
    - ✅ **Muestra métricas** en tiempo real
    
    ### 🚀 ¿Cómo usar?
    
    1. **Configura los IDs** de tus Google Sheets en el sidebar ←
    2. **Haz clic** en el botón "Ejecutar Cálculo de Promedios"
    3. **Espera** a que se procesen las 30 hojas
    4. **Revisa** los resultados en esta pantalla
    
    ### 📊 IDs de Google Sheets:
    
    - **Origen**: Donde están tus datos diarios (hojas por fecha)
    - **Destino**: Donde se guardarán los resultados del cálculo
    
    ### ⚠️ Requisitos:
    
    - Archivo `credentials.json` en la raíz del proyecto
    - Permisos de escritura en ambos Google Sheets
    - Conexión a internet
    """)

# Footer
st.markdown("---")
st.caption("📅 Última actualización: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))