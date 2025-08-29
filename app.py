import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import time
import pandas as pd

# Configuración básica de la página
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
        value="1TZo6pSlhoFFf00ruIv2dpjszHUMK4I9T_ZFQdo50jEk"
    )
    
    SPREADSHEET_ID_DESTINO = st.text_input(
        "💾 ID Spreadsheet Destino", 
        value="1DgZ7I5kRxOPXE0iQGfqalbkmaOLubBCFipAs7zWqb2g"
    )
    
    st.markdown("---")
    ejecutar = st.button("🚀 Ejecutar Cálculo", type="primary")

# Función simplificada para extraer promedios
def extract_promedio_final(worksheet):
    try:
        data = worksheet.get_all_values()
        if len(data) <= 1:
            return None
        
        # Buscar "Promedio:" en los datos
        for row in data:
            for i, cell in enumerate(row):
                if cell and 'promedio:' in cell.lower():
                    # Buscar valor en la celda siguiente
                    if i + 1 < len(row):
                        valor_cell = row[i + 1]
                        if valor_cell and '$' in valor_cell:
                            try:
                                # Limpiar y convertir el valor
                                valor_limpio = valor_cell.replace('$', '').replace('MXN', '')
                                valor_limpio = valor_limpio.replace('mxn', '').replace('MX', '')
                                valor_limpio = valor_limpio.replace(',', '').strip()
                                
                                if valor_limpio and valor_limpio.replace('.', '', 1).isdigit():
                                    return float(valor_limpio)
                            except ValueError:
                                continue
        return None
    except Exception:
        return None

# Función principal
def main():
    if ejecutar:
        if not SPREADSHEET_ID_ORIGEN or not SPREADSHEET_ID_DESTINO:
            st.error("❌ Por favor ingresa ambos IDs de Google Sheets")
            return
        
        try:
            # Autenticación
            SCOPES = ['https://www.googleapis.com/auth/spreadsheets',
                     'https://www.googleapis.com/auth/drive']
            
            credentials = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
            client = gspread.authorize(credentials)
            
            # Conectar a los spreadsheets
            spreadsheet_origen = client.open_by_key(SPREADSHEET_ID_ORIGEN)
            spreadsheet_destino = client.open_by_key(SPREADSHEET_ID_DESTINO)
            
            st.success("✅ Conexión exitosa con Google Sheets")
            
            # Obtener las últimas 30 hojas
            all_worksheets = spreadsheet_origen.worksheets()
            ultimas_hojas = all_worksheets[-30:] if len(all_worksheets) >= 30 else all_worksheets
            
            st.info(f"📑 Analizando {len(ultimas_hojas)} hojas...")
            
            # Extraer promedios
            promedios = []
            progress_bar = st.progress(0)
            
            for i, worksheet in enumerate(ultimas_hojas):
                progress_bar.progress((i + 1) / len(ultimas_hojas))
                promedio = extract_promedio_final(worksheet)
                if promedio is not None:
                    promedios.append(promedio)
                time.sleep(0.1)
            
            progress_bar.empty()
            
            if not promedios:
                st.error("❌ No se encontraron promedios en las hojas")
                return
            
            # Calcular resultados
            promedio_final = sum(promedios) / len(promedios)
            minimo = min(promedios)
            maximo = max(promedios)
            
            # Mostrar resultados
            st.success("✅ Cálculo completado exitosamente!")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📊 Promedio de Promedios", f"${promedio_final:,.2f} MXN")
            with col2:
                st.metric("📉 Mínimo", f"${minimo:,.2f} MXN")
            with col3:
                st.metric("📈 Máximo", f"${maximo:,.2f} MXN")
            
            # Guardar resultados
            try:
                worksheet_destino = spreadsheet_destino.sheet1
                existing_data = worksheet_destino.get_all_values()
                
                fecha_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                nuevos_datos = [fecha_str, promedio_final, minimo, maximo]
                
                if not existing_data:
                    encabezados = ["Fecha", "Promedio (MXN)", "Mínimo", "Máximo"]
                    worksheet_destino.update([encabezados, nuevos_datos])
                else:
                    worksheet_destino.append_row(nuevos_datos)
                
                st.success("💾 Resultados guardados en Google Sheets")
                
            except Exception as e:
                st.error(f"❌ Error al guardar: {str(e)}")
                
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
    
    else:
        # Pantalla de inicio
        st.markdown("""
        ## 🎯 Bienvenido al Sistema de Análisis de Precios
        
        ### 📋 ¿Qué hace esta aplicación?
        - ✅ **Calcula automáticamente** el promedio de promedios
        - ✅ **Extrae valores** de cada hoja de cálculo  
        - ✅ **Guarda resultados** en Google Sheets
        - ✅ **Muestra métricas** en tiempo real
        
        ### 🚀 ¿Cómo usar?
        1. **Configura los IDs** en el sidebar ←
        2. **Haz clic** en "Ejecutar Cálculo"
        3. **Espera** a que se procesen las hojas
        4. **Revisa** los resultados
        
        """)

# Ejecutar la aplicación
if __name__ == "__main__":
    main()

# Footer
st.markdown("---")
st.caption(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
