import streamlit as st
import pandas as pd
import gspread
from google.oauth2 import service_account
from datetime import datetime
import numpy as np
import re
from google.auth.transport.requests import Request

# Configuración de la página
st.set_page_config(
    page_title="Sistema de Análisis de Precios de Hoteles",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Título de la aplicación
st.title("🏨 Sistema de Análisis de Precios de Hoteles")

# IDs de las hojas de cálculo
SHEET_IDS = {
    "Mérida": "13tPaaJCX4o4HkxrRdPiuc5NDP3XhrJuvKdq83Eh7-KU",
    "Tuxtla": "1Stux8hR4IlZ879gL7TRbz3uKzputDVwR362VINUr5Ho"
}

# Configuración mejorada para acceso a Google Sheets
def setup_gspread():
    try:
        if 'gcp_service_account' not in st.secrets:
            st.error("No se encontraron las credenciales en los Secrets.")
            return None
        
        # Crear credenciales directamente desde el diccionario
        creds_dict = dict(st.secrets["gcp_service_account"])
        
        # Asegurar que la private key tenga el formato correcto
        if 'private_key' in creds_dict:
            creds_dict['private_key'] = creds_dict['private_key'].replace('\\n', '\n')
        
        # Crear credenciales
        creds = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=[
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive",
                "https://www.googleapis.com/auth/spreadsheets"
            ]
        )
        
        # Crear cliente gspread
        gc = gspread.service_account_from_dict(creds_dict)
        return gc
        
    except Exception as e:
        st.error(f"Error de autenticación: {e}")
        st.info("""
        **Solución de problemas:**
        1. Verifica que las credenciales sean correctas en Streamlit Secrets
        2. Asegúrate de que el servicio tenga acceso a los Google Sheets
        3. Revisa que el email del service account esté agregado como editor en los Sheets
        """)
        return None

# Función alternativa de autenticación
def setup_gspread_alternative():
    try:
        # Usar autenticación directa sin secrets (para debugging)
        try:
            # Intenta cargar desde secrets primero
            if 'gcp_service_account' in st.secrets:
                creds_info = dict(st.secrets["gcp_service_account"])
                creds_info['private_key'] = creds_info['private_key'].replace('\\n', '\n')
                gc = gspread.service_account_from_dict(creds_info)
                return gc
        except:
            pass
        
        # Fallback: intentar con acceso público
        st.warning("Usando modo de acceso público (funcionalidad limitada)")
        return None
        
    except Exception as e:
        st.error(f"Error alternativo de autenticación: {e}")
        return None

# Función para obtener datos con manejo robusto de errores
def get_sheet_data(worksheet):
    try:
        # Intentar obtener datos
        data = worksheet.get_all_records()
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        
        # Limpiar nombres de columnas
        df.columns = df.columns.str.strip()
        
        return df
        
    except Exception as e:
        st.error(f"Error al obtener datos de {worksheet.title}: {str(e)}")
        
        # Intentar método alternativo para esta hoja
        try:
            # Obtener todos los valores y crear DataFrame manualmente
            all_values = worksheet.get_all_values()
            if len(all_values) > 1:
                headers = all_values[0]
                data = all_values[1:]
                df = pd.DataFrame(data, columns=headers)
                return df
        except Exception as inner_e:
            st.error(f"Error alternativo también falló: {inner_e}")
        
        return pd.DataFrame()

# Función mejorada para obtener todas las hojas
def get_all_sheets(spreadsheet_id, client):
    try:
        if client is None:
            st.error("Cliente no autenticado")
            return None
            
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheets = spreadsheet.worksheets()
        
        # Ordenar hojas por título (asumiendo que contienen fechas)
        try:
            worksheets.sort(key=lambda x: x.title, reverse=True)
        except:
            pass  # Si no se pueden ordenar, continuar sin ordenar
            
        return {f"{ws.title}": ws for ws in worksheets}
        
    except Exception as e:
        st.error(f"Error al acceder al spreadsheet {spreadsheet_id}: {e}")
        
        # Intentar con método alternativo
        try:
            spreadsheet = client.open_by_key(spreadsheet_id)
            worksheets = spreadsheet.worksheets()
            return {f"{ws.title}": ws for ws in worksheets}
        except:
            return None

# Función mejorada para detectar columnas
def detect_columns(df):
    if df.empty:
        return None, None
        
    hotel_keywords = ['hotel', 'nombre', 'name', 'establecimiento', 'property', 'hotel_name']
    price_keywords = ['precio', 'price', 'costo', 'cost', 'valor', 'value', 'monto', 'amount', 'importe', 'rate', 'tarifa']
    
    # Buscar columnas por nombre exacto primero
    for col in df.columns:
        col_lower = str(col).lower()
        
        if any(keyword == col_lower for keyword in hotel_keywords):
            hotel_col = col
            break
    else:
        # Búsqueda parcial si no se encuentra exacto
        for col in df.columns:
            col_lower = str(col).lower()
            if any(keyword in col_lower for keyword in hotel_keywords):
                hotel_col = col
                break
        else:
            hotel_col = None
    
    # Buscar columna de precio
    for col in df.columns:
        col_lower = str(col).lower()
        
        if any(keyword == col_lower for keyword in price_keywords):
            price_col = col
            break
    else:
        for col in df.columns:
            col_lower = str(col).lower()
            if any(keyword in col_lower for keyword in price_keywords):
                price_col = col
                break
        else:
            price_col = None
    
    return hotel_col, price_col

# Función para buscar hotel con manejo robusto de errores
def search_hotel_in_sheets(client, spreadsheet_id, hotel_name, max_sheets=10):
    try:
        if client is None:
            st.error("No hay conexión con Google Sheets")
            return []
        
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheets = spreadsheet.worksheets()
        
        # Limitar número de hojas para no sobrecargar
        worksheets = worksheets[:max_sheets]
        resultados = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, worksheet in enumerate(worksheets):
            status_text.text(f"Buscando en hoja {i+1}/{len(worksheets)}: {worksheet.title}")
            progress_bar.progress((i + 1) / len(worksheets))
            
            try:
                df = get_sheet_data(worksheet)
                if df.empty:
                    continue
                
                hotel_col, price_col = detect_columns(df)
                
                if hotel_col and price_col:
                    # Búsqueda case-insensitive
                    mask = df[hotel_col].astype(str).str.lower().str.contains(hotel_name.lower(), na=False)
                    
                    if mask.any():
                        for _, row in df[mask].iterrows():
                            try:
                                precio_val = str(row[price_col])
                                # Limpiar precio
                                precio_limpio = pd.to_numeric(
                                    re.sub(r'[^\d.,]', '', precio_val).replace(',', '.'),
                                    errors='coerce'
                                )
                                
                                if not pd.isna(precio_limpio) and precio_limpio > 0:
                                    resultados.append({
                                        'hoja': worksheet.title,
                                        'hotel': row[hotel_col],
                                        'precio': precio_limpio
                                    })
                            except:
                                continue
                
            except Exception as e:
                continue  # Continuar con la siguiente hoja si hay error
        
        progress_bar.empty()
        status_text.empty()
        
        return resultados
        
    except Exception as e:
        st.error(f"Error en la búsqueda: {e}")
        return []

# Interfaz principal mejorada
def main():
    st.sidebar.header("📍 Selecciona Ubicación")
    ubicacion = st.sidebar.radio("Ubicación:", ["Mérida", "Tuxtla"], index=0)
    
    spreadsheet_id = SHEET_IDS[ubicacion]
    
    # Obtener cliente
    client = setup_gspread()
    if client is None:
        client = setup_gspread_alternative()
    
    # Búsqueda de hotel
    st.header("🔍 Búsqueda de Hotel")
    hotel_busqueda = st.text_input("Nombre del hotel:")
    
    if hotel_busqueda.strip() and client:
        resultados = search_hotel_in_sheets(client, spreadsheet_id, hotel_busqueda, 15)
        
        if resultados:
            st.success(f"✅ Encontrados {len(resultados)} precios")
            
            # Calcular métricas
            precios = [r['precio'] for r in resultados]
            hojas_unicas = len(set(r['hoja'] for r in resultados))
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Precio Mínimo", f"${min(precios):,.2f}")
            with col2:
                st.metric("Precio Máximo", f"${max(precios):,.2f}")
            with col3:
                st.metric("Promedio", f"${sum(precios)/len(precios):,.2f}")
            with col4:
                st.metric("Hojas", hojas_unicas)
            
            # Mostrar resultados
            st.dataframe(pd.DataFrame(resultados))
        else:
            st.warning("No se encontraron resultados")
    
    # Análisis individual de hojas
    st.header("📊 Análisis Individual por Hoja")
    
    if client:
        sheets_dict = get_all_sheets(spreadsheet_id, client)
        if sheets_dict:
            sheet_names = list(sheets_dict.keys())
            selected_sheet = st.selectbox("Selecciona una hoja:", sheet_names)
            
            if selected_sheet:
                df = get_sheet_data(sheets_dict[selected_sheet])
                if not df.empty:
                    st.dataframe(df)
                    
                    hotel_col, price_col = detect_columns(df)
                    if hotel_col and price_col:
                        st.info(f"Columnas detectadas: {hotel_col}, {price_col}")
    else:
        st.warning("No se pudo conectar para cargar hojas individuales")

# Información
st.sidebar.info("""
**Solución de problemas:**
- Verifica que el service account tenga acceso a los Sheets
- Revisa que las credenciales en Secrets sean correctas
- Los Sheets deben ser compartidos con el service account
""")

if __name__ == "__main__":
    main()
