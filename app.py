import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import time
import pandas as pd
import numpy as np
import os
import re
import random
import pytz
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from fake_useragent import UserAgent
from oauth2client.service_account import ServiceAccountCredentials

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
        **Versión:** 3.0
        **Función:** Calcula el promedio de promedios + Scraper Booking.com
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
    .scraper-status {
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
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
    
    # Selector de funcionalidad principal
    funcion = st.selectbox(
        "Selecciona la operación:",
        ["Calcular Promedio de Promedios", "Solo Mostrar Datos", "Debug: Ver estructura de hojas", "Scraper Booking.com"]
    )
    
    st.markdown("---")
    
    # Configuración para análisis de promedios
    if funcion != "Scraper Booking.com":
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
        
        # Opciones avanzadas
        with st.expander("⚡ Opciones avanzadas"):
            umbral_minimo = st.number_input("Umbral mínimo ($)", value=1000, help="Valor mínimo para considerar como promedio válido")
            umbral_maximo = st.number_input("Umbral máximo ($)", value=5000000, help="Valor máximo para considerar como promedio válido")
            buscar_en_toda_hoja = st.checkbox("Buscar en toda la hoja", value=True, help="Buscar valores numéricos en todas las celdas")
    
    # Configuración para el scraper de Booking.com
    else:
        st.subheader("🔧 Configuración del Scraper")
        
        SPREADSHEET_ID_SCRAPER = st.text_input(
            "📋 ID Spreadsheet para Scraper",
            value="13tPaaJCX4o4HkxrRdPiuc5NDP3XhrJuvKdq83Eh7-KU",
            help="ID del Google Sheet donde se guardarán los datos del scraper"
        )
        
        MAX_RESULTS = st.number_input("Máximo de resultados", value=150, min_value=10, max_value=500, help="Número máximo de hoteles a scrapear")
        
        st.markdown("---")
        st.info("💡 El scraper abrirá una ventana de Chrome automáticamente")
    
    st.markdown("---")
    
    # Botón de ejecución
    ejecutar = st.button("🚀 Ejecutar", type="primary", use_container_width=True)
    
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
# FUNCIONES DEL SCRAPER DE BOOKING.COM
# =============================================================================
def init_google_sheets_scraper():
    """Inicializa la conexión con Google Sheets para el scraper"""
    try:
        SCOPES = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        
        if 'google_credentials' not in st.secrets:
            st.error("❌ No se encontraron credenciales en Secrets para el scraper.")
            return None
            
        creds_dict = dict(st.secrets["google_credentials"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPES)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"❌ Error en autenticación del scraper: {str(e)}")
        return None

def create_daily_sheet(spreadsheet):
    """Crea una nueva hoja con el orden de columnas solicitado"""
    try:
        today = datetime.now(pytz.timezone('America/Mexico_City')).strftime('%Y-%m-%d')
        try:
            worksheet = spreadsheet.add_worksheet(title=today, rows=MAX_RESULTS+10, cols=10)
        except:
            worksheet = spreadsheet.worksheet(today)
        
        # Orden modificado según lo solicitado
        headers = ['Nombre', 'Precio (MXN)', 'Puntuación', 'Comentarios', 'Fecha']
        if worksheet.row_count < 1 or worksheet.row_values(1) != headers:
            worksheet.insert_row(headers, 1)
        
        return worksheet
    except Exception as e:
        st.error(f"❌ Error al crear hoja: {e}")
        return None

def init_driver():
    """Inicializa el navegador Chrome"""
    try:
        chrome_options = Options()
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_experimental_option("detach", True)
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--lang=es")
        
        # Configurar User-Agent aleatorio
        ua = UserAgent()
        chrome_options.add_argument(f"user-agent={ua.random}")
        
        # Inicializar el driver
        service = Service()
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.implicitly_wait(15)
        return driver
    except Exception as e:
        st.error(f"❌ Error al iniciar ChromeDriver: {e}")
        return None

def check_for_captcha(driver):
    """Verifica si hay CAPTCHA presente"""
    try:
        captcha_frame = driver.find_element(By.XPATH, '//iframe[contains(@title, "CAPTCHA")]')
        if captcha_frame:
            st.warning("⚠️ CAPTCHA Detectado! Se requiere intervención manual")
            st.info("Por favor resuelve el CAPTCHA en la ventana del navegador...")
            return True
    except:
        pass
    return False

def accept_cookies(driver):
    """Maneja el popup de consentimiento de cookies"""
    try:
        cookie_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, 'onetrust-accept-btn-handler')))
        ActionChains(driver).move_to_element(cookie_btn).pause(1).click().perform()
        st.success("✓ Cookies aceptadas")
        time.sleep(2)
    except:
        pass

def load_more_results(driver, SCROLL_PAUSE=2, SCROLL_ATTEMPTS=10):
    """Hace scroll para cargar más resultados en la misma página"""
    last_height = driver.execute_script("return document.body.scrollHeight")
    attempts = 0
    
    while attempts < SCROLL_ATTEMPTS:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE)
        
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            attempts += 1
            st.write(f"Intento {attempts}/{SCROLL_ATTEMPTS}: No se cargaron más resultados")
        else:
            attempts = 0
            st.success("✓ Se cargaron más resultados")
        
        last_height = new_height
        
        hotels = driver.find_elements(By.CSS_SELECTOR, '[data-testid="property-card"]')
        if len(hotels) >= MAX_RESULTS:
            st.info(f"Se alcanzó el límite de {MAX_RESULTS} hoteles")
            break
    
    return driver.find_elements(By.CSS_SELECTOR, '[data-testid="property-card"]')

def get_hotel_data(hotel_element):
    """Extrae datos del hotel sin información de distancia"""
    data = {
        'nombre': 'N/A',
        'puntuacion': 'N/A',
        'comentarios': 'N/A',
        'precio': 'N/A'
    }
    
    # Extracción del nombre
    try:
        name = hotel_element.find_element(By.CSS_SELECTOR, '[data-testid="title"]').text
        data['nombre'] = name.strip()
    except Exception as e:
        st.error(f"Error al extraer nombre: {str(e)}")
    
    # Extracción de puntuación y comentarios
    try:
        score_element = hotel_element.find_element(By.CSS_SELECTOR, '[data-testid="review-score"]')
        
        # Extraer puntuación numérica
        try:
            score_number = score_element.find_element(By.CSS_SELECTOR, 'div[aria-hidden="true"]').text
            data['puntuacion'] = score_number.replace(',', '.')
        except:
            pass
        
        # Extraer comentarios
        try:
            score_text = score_element.find_element(By.CSS_SELECTOR, 'div[aria-hidden="false"]').text
            if '·' in score_text:
                parts = score_text.split('·')
                if len(parts) > 1:
                    data['comentarios'] = ''.join(c for c in parts[1] if c.isdigit())
        except:
            pass
    except Exception as e:
        st.error(f"Error al extraer puntuación: {str(e)}")
    
    # Extracción de precio
    try:
        price_element = hotel_element.find_element(By.CSS_SELECTOR, '[data-testid="price-and-discounted-price"]')
        price_text = price_element.text
        data['precio'] = ''.join(c for c in price_text if c.isdigit())
    except:
        try:
            price_element = hotel_element.find_element(By.CSS_SELECTOR, '.bui-price-display__value')
            price_text = price_element.text
            data['precio'] = ''.join(c for c in price_text if c.isdigit())
        except Exception as e:
            st.error(f"Error al extraer precio: {str(e)}")
    
    return data

def run_booking_scraper():
    """Función principal de scraping con el nuevo orden de columnas"""
    st.header("🏨 Scraper de Booking.com - Mérida")
    
    # Inicializar Google Sheets
    client = init_google_sheets_scraper()
    if not client:
        return 0
    
    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID_SCRAPER)
    except Exception as e:
        st.error(f"❌ Error al abrir la hoja de cálculo: {str(e)}")
        return 0
    
    worksheet = create_daily_sheet(spreadsheet)
    if not worksheet:
        return 0
    
    # Inicializar el navegador
    with st.spinner("🖥️ Iniciando navegador Chrome..."):
        driver = init_driver()
        if not driver:
            return 0
    
    try:
        # Parámetros de búsqueda
        params = {
            'ss': "Merida",
            'lang': 'es',
            'checkin': datetime.now().strftime('%Y-%m-%d'),
            'checkout': (datetime.now().date() + pd.Timedelta(days=1)).strftime('%Y-%m-%d'),
            'group_adults': '2',
            'no_rooms': '1'
        }
        
        BASE_URL = "https://www.booking.com"
        url = f"{BASE_URL}/searchresults.es.html?{'&'.join(f'{k}={v}' for k,v in params.items())}"
        
        st.info(f"🌐 Cargando página: {url}")
        
        driver.get(url)
        time.sleep(5)
        
        if check_for_captcha(driver):
            time.sleep(10)
        
        accept_cookies(driver)
        
        st.info("⬇️ Haciendo scroll para cargar más resultados...")
        hotel_elements = load_more_results(driver)
        hotel_elements = hotel_elements[:MAX_RESULTS]
        
        st.success(f"🏨 Total de hoteles cargados: {len(hotel_elements)}")
        
        # Barra de progreso
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        hotels_added = 0
        for i, element in enumerate(hotel_elements):
            if hotels_added >= MAX_RESULTS:
                break
            
            try:
                hotel_data = get_hotel_data(element)
                extraction_time = datetime.now(pytz.timezone('America/Mexico_City')).strftime('%Y-%m-%d %H:%M:%S')
                
                # Insertar en el nuevo orden solicitado
                worksheet.append_row([
                    hotel_data['nombre'],      # Nombre
                    hotel_data['precio'],     # Precio
                    hotel_data['puntuacion'], # Puntuación
                    hotel_data['comentarios'],# Comentarios
                    extraction_time          # Fecha
                ])
                
                hotels_added += 1
                
                # Actualizar barra de progreso
                progress = (i + 1) / len(hotel_elements)
                progress_bar.progress(progress)
                status_text.text(f"Procesando hotel {i+1}/{len(hotel_elements)}: {hotel_data['nombre'][:30]}...")
                
                st.write(f"✅ Añadido #{hotels_added}: {hotel_data['nombre'][:50]}... - Precio: {hotel_data['precio']} MXN - Puntuación: {hotel_data['puntuacion']} ({hotel_data['comentarios']} comentarios)")
                
                time.sleep(random.uniform(1, 3))
                
            except Exception as e:
                st.error(f"❌ Error procesando hotel: {str(e)}")
                continue
        
        st.success(f"🔍 Scraping completado. Hoteles totales: {hotels_added}")
        return hotels_added
        
    except Exception as e:
        st.error(f"❌ Error fatal: {str(e)}")
        return 0
    finally:
        if 'driver' in locals():
            st.info("🖥️ El navegador permanecerá abierto...")
            # No cerramos el navegador para permitir interacción manual si es necesario

# =============================================================================
# LÓGICA PRINCIPAL DE LA APLICACIÓN
# =============================================================================
def main():
    if ejecutar:
        # Autenticación
        client, success = authenticate_google_sheets()
        if not success:
            return
        
        # Ejecutar según la opción seleccionada
        if funcion == "Calcular Promedio de Promedios":
            if not SPREADSHEET_ID_ORIGEN or not SPREADSHEET_ID_DESTINO:
                st.error("❌ Por favor ingresa ambos IDs de Google Sheets")
                return
                
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
            
        elif funcion == "Scraper Booking.com":
            start_time = time.time()
            total_hotels = run_booking_scraper()
            elapsed_time = (time.time() - start_time) / 60
            
            st.success("🎉 Reporte final:")
            st.metric("⏱️ Duración", f"{elapsed_time:.2f} minutos")
            st.metric("🏨 Hoteles recolectados", total_hotels)
            st.info(f"📊 Hoja de cálculo: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID_SCRAPER}")
    
    else:
        # PANTALLA DE INICIO
        st.markdown("""
        ## 🎯 Bienvenido al Sistema de Análisis de Precios Mérida - v3.0
        
        ### 🆕 ¿Qué hay de nuevo?
        
        - **🔍 Búsqueda inteligente**: Detecta "Promedio:" en diferentes formatos
        - **🏨 Scraper Booking.com**: Nueva función para extraer datos de hoteles
        - **📊 Análisis avanzado**: Busca en celdas adyacentes y en toda la hoja
        - **⚡ Opciones configurables**: Ajusta umbrales y métodos de búsqueda
        - **🐛 Modo Debug**: Analiza la estructura de tus hojas
        
        ### 🚀 ¿Cómo usar?
        
        1. **Selecciona** la operación deseada en el sidebar ←
        2. **Configura los parámetros** según la operación
        3. **Haz clic** en "Ejecutar"
        4. **Revisa** los resultados y el feedback
        
        ### 💡 Consejos:
        
        - Para el scraper: Asegúrate de tener Chrome instalado
        - Usa **"Debug: Ver estructura de hojas"** si no encuentra los promedios
        - Ajusta los **umbrales** si los valores están fuera del rango esperado
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
st.caption("⚡ Powered by Streamlit + Google Sheets API + Selenium | 🆕 v3.0 con scraper")
