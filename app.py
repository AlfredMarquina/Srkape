import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import time
import pandas as pd
import numpy as np
import os
import re

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
        **Versión:** 2.0
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
    .success-box {
        background-color: #d4edda;
        color: #155724;
        padding: 10px;
        border-radius: 5px;
        border: 1px solid #c3e6cb;
        margin: 5px 0;
    }
    .warning-box {
        background-color: #fff3cd;
        color: #856404;
        padding: 10px;
        border-radius: 5px;
        border: 1px solid #ffeeba;
        margin: 5px 0;
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
        ["Calcular Promedio de Promedios", "Solo Mostrar Datos", "Debug: Ver estructura de hojas"]
    )
    
    st.markdown("---")
    
    # Opciones avanzadas
    with st.expander("⚡ Opciones avanzadas"):
        umbral_minimo = st.number_input("Umbral mínimo ($)", value=1000, help="Valor mínimo para considerar como promedio válido")
        umbral_maximo = st.number_input("Umbral máximo ($)", value=5000000, help="Valor máximo para considerar como promedio válido")
        buscar_en_toda_hoja = st.checkbox("Buscar en toda la hoja", value=True, help="Buscar valores numéricos en todas las celdas")
    
    st.markdown("---")
    
    # Botón de ejecución
    ejecutar = st.button("🚀 Ejecutar Análisis", type="primary", use_container_width=True)
    
    st.markdown("---")
    st.info("💡 Asegúrate de que las hojas tengan datos y el formato correcto")

# =============================================================================
# FUNCIONES PRINCIPALES - MEJORADAS
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

def extraer_valor_numerico(valor_cell):
    """Extraer valor numérico de una celda"""
    try:
        if not valor_cell:
            return None
            
        # Limpiar el valor
        valor_limpio = str(valor_cell).replace('$', '').replace('MXN', '')
        valor_limpio = valor_limpio.replace('mxn', '').replace('MX', '')
        valor_limpio = valor_limpio.replace(',', '').replace(' ', '')
        valor_limpio = valor_limpio.replace('USD', '').replace('usd', '')
        valor_limpio = valor_limpio.replace('(', '').replace(')', '')
        
        # Buscar números con expresiones regulares
        numeros = re.findall(r'[-+]?\d*\.\d+|\d+', valor_limpio)
        
        if numeros:
            # Tomar el primer número encontrado (generalmente es el principal)
            numero = float(numeros[0])
            
            # Filtrar valores razonables para promedios
            if umbral_minimo <= numero <= umbral_maximo:
                return numero
    
    except (ValueError, TypeError):
        pass
    
    return None

def extract_promedio_final(worksheet):
    """Extraer el valor del promedio final de una hoja - VERSIÓN MEJORADA"""
    try:
        data = worksheet.get_all_values()
        
        if len(data) <= 1:
            st.sidebar.warning(f"📄 '{worksheet.title}': Muy pocos datos")
            return None
        
        # Buscar "Promedio:" en diferentes formatos y posiciones
        posibles_palabras_clave = [
            'promedio', 'promedio:', 'promedio final', 'total', 'suma',
            'average', 'mean', 'total:', 'resultado', 'valor final',
            'importe', 'monto', 'cantidad', 'valor', 'precio'
        ]
        
        # Buscar en todas las celdas
        for row_idx, row in enumerate(data):
            for col_idx, cell in enumerate(row):
                cell_value = str(cell).strip().lower() if cell else ""
                
                # Verificar si contiene alguna palabra clave
                if any(keyword in cell_value for keyword in posibles_palabras_clave):
                    # Buscar valor numérico en celdas adyacentes
                    direcciones = [
                        (0, 1),   # Derecha
                        (1, 0),   # Abajo
                        (0, -1),  # Izquierda
                        (-1, 0),  # Arriba
                        (1, 1),   # Diagonal inferior derecha
                        (1, -1),  # Diagonal inferior izquierda
                    ]
                    
                    for dr, dc in direcciones:
                        new_row, new_col = row_idx + dr, col_idx + dc
                        if (0 <= new_row < len(data) and 
                            0 <= new_col < len(row) and 
                            data[new_row][new_col]):
                            
                            valor_cell = data[new_row][new_col]
                            promedio = extraer_valor_numerico(valor_cell)
                            if promedio is not None:
                                st.sidebar.success(f"✅ '{worksheet.title}': ${promedio:,.2f} (encontrado cerca de '{cell}')")
                                return promedio
        
        # Si no se encontró y está habilitado, buscar patrones numéricos en toda la hoja
        if buscar_en_toda_hoja:
            st.sidebar.info(f"🔍 Buscando patrones en '{worksheet.title}'...")
            return buscar_patrones_numericos(data, worksheet.title)
        else:
            st.sidebar.warning(f"⚠️ '{worksheet.title}': No se encontró 'Promedio:'")
            return None
        
    except Exception as e:
        st.error(f"Error procesando hoja '{worksheet.title}': {str(e)}")
        return None

def buscar_patrones_numericos(data, nombre_hoja):
    """Buscar patrones numéricos en toda la hoja"""
    valores_encontrados = []
    
    for row_idx, row in enumerate(data):
        for col_idx, cell in enumerate(row):
            if cell:
                valor = extraer_valor_numerico(cell)
                if valor is not None:
                    valores_encontrados.append({
                        'valor': valor,
                        'fila': row_idx + 1,
                        'columna': col_idx + 1,
                        'celda': cell
                    })
    
    if valores_encontrados:
        # Ordenar por valor y tomar el más grande (generalmente es el total/promedio)
        valores_encontrados.sort(key=lambda x: x['valor'], reverse=True)
        mayor_valor = valores_encontrados[0]
        
        st.sidebar.success(f"🔢 '{nombre_hoja}': ${mayor_valor['valor']:,.2f} (fila {mayor_valor['fila']}, col {mayor_valor['columna']})")
        return mayor_valor['valor']
    
    st.sidebar.warning(f"❌ '{nombre_hoja}': No se encontraron valores numéricos")
    return None

def calculate_promedio_de_promedios(client, spreadsheet_id_origen):
    """Calcular el promedio de los promedios finales - VERSIÓN MEJORADA"""
    try:
        spreadsheet_origen = client.open_by_key(spreadsheet_id_origen)
        all_worksheets = spreadsheet_origen.worksheets()
        
        # Filtrar solo hojas que parezcan ser de fechas (nombres con números)
        hojas_fechas = [ws for ws in all_worksheets if any(c.isdigit() for c in ws.title)]
        ultimas_hojas = hojas_fechas[-30:] if len(hojas_fechas) >= 30 else hojas_fechas
        
        st.info(f"📑 Analizando {len(ultimas_hojas)} hojas de fechas...")
        
        promedios_finales = []
        hojas_procesadas = []
        hojas_sin_datos = []
        
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
            else:
                hojas_sin_datos.append(worksheet.title)
            
            time.sleep(0.1)
        
        # Limpiar barra de progreso
        progress_bar.empty()
        status_text.empty()
        
        # Mostrar resumen de hojas sin datos
        if hojas_sin_datos:
            with st.expander("📋 Hojas sin promedios encontrados", expanded=True):
                st.warning(f"Se encontraron {len(hojas_sin_datos)} hojas sin promedios:")
                for hoja in hojas_sin_datos:
                    st.write(f"• {hoja}")
        
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
            'hojas_sin_promedio': len(hojas_sin_datos),
            'promedios_individuales': promedios_finales,
            'nombres_hojas': hojas_procesadas,
            'hojas_sin_datos': hojas_sin_datos,
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
            results['hojas_con_promedio'],
            results['hojas_sin_promedio']
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
                "Total Hojas Analizadas",
                "Hojas con Promedio",
                "Hojas sin Promedio"
            ]
            worksheet.update([encabezados, datos])
        else:
            # Agregar nueva fila
            worksheet.append_row(datos)
        
        return True
        
    except Exception as e:
        st.error(f"❌ Error al guardar resultados: {str(e)}")
        return False

def debug_hojas(client, spreadsheet_id_origen):
    """Función de debug para ver la estructura de las hojas"""
    try:
        spreadsheet = client.open_by_key(spreadsheet_id_origen)
        hojas = spreadsheet.worksheets()
        
        st.subheader("🔍 Debug: Estructura de Hojas")
        st.info(f"Total de hojas encontradas: {len(hojas)}")
        
        for i, hoja in enumerate(hojas[:5]):  # Mostrar solo las primeras 5 para no saturar
            with st.expander(f"Hoja: {hoja.title}"):
                try:
                    datos = hoja.get_all_values()
                    st.write(f"Filas: {len(datos)}, Columnas: {len(datos[0]) if datos else 0}")
                    
                    # Mostrar primeras 5 filas
                    if datos:
                        st.write("**Primeras 5 filas:**")
                        for j, fila in enumerate(datos[:5]):
                            st.write(f"Fila {j+1}: {fila}")
                    
                    # Buscar celdas que contengan "promedio"
                    celdas_promedio = []
                    for row_idx, row in enumerate(datos):
                        for col_idx, cell in enumerate(row):
                            if cell and 'promedio' in str(cell).lower():
                                celdas_promedio.append({
                                    'fila': row_idx + 1,
                                    'columna': col_idx + 1,
                                    'valor': cell,
                                    'valores_adyacentes': []
                                })
                    
                    if celdas_promedio:
                        st.success("**¡Se encontraron celdas con 'promedio'!**")
                        for celda in celdas_promedio:
                            st.write(f"Fila {celda['fila']}, Col {celda['columna']}: `{celda['valor']}`")
                    
                except Exception as e:
                    st.error(f"Error al leer hoja: {str(e)}")
        
    except Exception as e:
        st.error(f"❌ Error en debug: {str(e)}")

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
                    col4, col5, col6 = st.columns(3)
                    with col4:
                        st.info(f"📋 Total de hojas analizadas: {resultados['total_hojas']}")
                    with col5:
                        st.success(f"✅ Hojas con promedio: {resultados['hojas_con_promedio']}")
                    with col6:
                        st.warning(f"⚠️ Hojas sin promedio: {resultados['hojas_sin_promedio']}")
                    
                    # Guardar resultados
                    with st.spinner("💾 Guardando resultados..."):
                        if save_results_to_sheet(client, SPREADSHEET_ID_DESTINO, resultados):
                            st.success("✅ Resultados guardados en Google Sheets")
                    
                    # Mostrar algunos promedios individuales
                    with st.expander("📋 Ver promedios individuales", expanded=True):
                        for i, (nombre, promedio) in enumerate(zip(resultados['nombres_hojas'], resultados['promedios_individuales'])):
                            st.write(f"**{nombre}**: ${promedio:,.2f} MXN")
        
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
        
        elif funcion == "Debug: Ver estructura de hojas":
            debug_hojas(client, SPREADSHEET_ID_ORIGEN)
    
    else:
        # PANTALLA DE INICIO
        st.markdown("""
        ## 🎯 Bienvenido al Sistema de Análisis de Precios Mérida - v2.0
        
        ### 🆕 ¿Qué hay de nuevo?
        
        - **🔍 Búsqueda inteligente**: Detecta "Promedio:" en diferentes formatos
        - **📊 Análisis avanzado**: Busca en celdas adyacentes y en toda la hoja
        - **⚡ Opciones configurables**: Ajusta umbrales y métodos de búsqueda
        - **🐛 Modo Debug**: Analiza la estructura de tus hojas
        
        ### 🚀 ¿Cómo usar?
        
        1. **Configura los IDs** de tus Google Sheets en el sidebar ←
        2. **Selecciona** la operación deseada
        3. **Ajusta opciones** si es necesario
        4. **Haz clic** en "Ejecutar Análisis"
        5. **Revisa** los resultados y el feedback en el sidebar
        
        ### 💡 Consejos:
        
        - Usa **"Debug: Ver estructura de hojas"** si no encuentra los promedios
        - Ajusta los **umbrales** si los valores están fuera del rango esperado
        - Revisa el **sidebar** para ver el progreso en tiempo real
        """)

# =============================================================================
# EJECUCIÓN DE LA APLICACIÓN
# =============================================================================
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"❌ Error inesperado: {str(e)}")
        st.info("🔄 Por favor recarga la página")

# =============================================================================
# FOOTER
# =============================================================================
st.markdown("---")
st.caption(f"📅 Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.caption("⚡ Powered by Streamlit + Google Sheets API | 🆕 v2.0 con búsqueda inteligente")
