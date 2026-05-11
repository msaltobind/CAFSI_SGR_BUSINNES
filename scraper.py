import pandas as pd
import json
import os
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import os



def obtener_archivo_cafci():
    # REEMPLAZA ESTA URL por la página exacta de CAFCI que me mencionaste
    url_pagina = "https://www.cafci.org.ar/index.html" 
    
    print("[+] Buscando el archivo de hoy en CAFCI...")
    try:
        # 1. Entramos a la página simulando ser un navegador normal
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        respuesta = requests.get(url_pagina, headers=headers)
        soup = BeautifulSoup(respuesta.text, 'html.parser')
        
        # 2. Buscamos dinámicamente el link que termine en .xlsx o diga "descargar"
        link_dinamico = None
        for enlace in soup.find_all('a', href=True):
            href = enlace['href'].lower()
            texto = enlace.text.lower()
            # Ajusta estas palabras clave si el botón en la web dice otra cosa
            if '.xlsx' in href or 'descargar' in texto or 'planilla' in texto: 
                link_dinamico = enlace['href']
                break
        
        if not link_dinamico:
            print("[-] No se encontró el botón de descarga dinámico hoy.")
            return None
            
        # Si el link es relativo (ej: /descargas/archivo.xlsx), le pegamos el dominio
        if link_dinamico.startswith('/'):
            link_dinamico = "https://www.cafci.org.ar" + link_dinamico
            
        print(f"[+] Link dinámico encontrado: {link_dinamico}")
        
        # 3. Descargamos el Excel de hoy
        respuesta_excel = requests.get(link_dinamico, headers=headers)
        
        # Le ponemos la fecha de hoy al nombre para no sobreescribir los viejos
        fecha_hoy = datetime.now().strftime("%Y%m%d")
        nombre_archivo = f"CAFCI_{fecha_hoy}.xlsx"
        
        with open(nombre_archivo, 'wb') as f:
            f.write(respuesta_excel.content)
            
        print(f"[+] Archivo descargado y guardado como: {nombre_archivo}")
        return nombre_archivo
        
    except Exception as e:
        print(f"[-] Error durante la descarga web: {e}")
        return None

def procesar_etl(ruta_archivo):
    print("[+] Extrayendo toda la base para el Dashboard de Investigación...")
    df = pd.read_excel(ruta_archivo, skiprows=7, header=[0, 1])
    
    nuevas_columnas = []
    for col_principal, col_secundaria in df.columns:
        if "Unnamed" in str(col_secundaria):
            nuevas_columnas.append(str(col_principal).strip())
        else:
            nuevas_columnas.append(f"{col_principal}_{col_secundaria}".strip())
    df.columns = nuevas_columnas
    
    # Mapeo de columnas
    col_fondo = next(c for c in df.columns if 'Fondo' in c and 'Moneda' not in c)
    col_sg = next(c for c in df.columns if 'Sociedad Gerente' in c)
    col_sd = next(c for c in df.columns if 'Sociedad Depositaria' in c)
    col_patrimonio = next(c for c in df.columns if 'Patrimonio_Actual' in c or 'Patrimonio' in c)
    
    columnas_negocio = [
        col_fondo, col_sg, col_sd, col_patrimonio, 
        'Honorarios Adm. SG', 'Honorarios Adm. SD', 
        'Gastos Ord Gestion', 'Comision Rescate'
    ]
    
    df_limpio = df[columnas_negocio].copy()
    df_limpio.columns = ['Fondo', 'Sociedad_Gerente', 'Sociedad_Depositaria', 'Patrimonio', 'Hon_SG', 'Hon_SD', 'Gastos_Gestion', 'Com_Rescate']
    
    df_limpio = df_limpio.dropna(subset=['Fondo', 'Patrimonio'])
    df_limpio['Patrimonio'] = pd.to_numeric(df_limpio['Patrimonio'], errors='coerce').fillna(0)
    
    # Extraer Sociedades Depositarias únicas y ordenadas
    depositarias = sorted(df_limpio['Sociedad_Depositaria'].dropna().unique().tolist())
    
    # Convertir NaN a 0 en las comisiones para evitar errores en JS
    comisiones = ['Hon_SG', 'Hon_SD', 'Gastos_Gestion', 'Com_Rescate']
    df_limpio[comisiones] = df_limpio[comisiones].fillna(0)
    
    datos_json = {
        "fecha_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "depositarias_unicas": depositarias,
        "fondos": df_limpio.to_dict(orient='records') # Mandamos TODA la base
    }
    
    os.makedirs("docs", exist_ok=True)
    with open('docs/data.json', 'w', encoding='utf-8') as f:
        json.dump(datos_json, f, ensure_ascii=False, indent=4)
    print("[+] Base generada exitosamente en docs/data.json")

if __name__ == "__main__":
    archivo = obtener_archivo_cafci()
    if archivo:
        procesar_etl(archivo)