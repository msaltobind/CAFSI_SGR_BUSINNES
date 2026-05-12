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
        
        # ... dentro de la función obtener_archivo_cafci ...
        links = []
        for enlace in soup.find_all('a', href=True):
            href = enlace['href']
            texto = enlace.text.lower()
            # Buscamos links que sean de Excel y no sean de manuales o instructivos
            if '.xlsx' in href.lower() and ('planilla' in texto or 'diaria' in texto):
                links.append(href)
        
        if not links:
            print("[-] No se encontraron links válidos.")
            return None
            
        # Tomamos el ÚLTIMO link de la lista, que suele ser el más nuevo en CAFCI
        link_dinamico = links[0] 
        # Si ves que sigue bajando el viejo, prueba cambiar links[0] por links[-1]
            
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
    
    # Capturamos la hora actual (ajustada a Argentina si prefieres, o UTC)
    fecha_ejecucion = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    datos_json = {
        "fecha_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "debug_id": datetime.now().timestamp(), # Esto obliga a Git a ver un cambio siempre
        "archivo_origen": os.path.basename(ruta_archivo),
        "fondos": df_limpio.to_dict(orient='records')
    }

    with open('docs/data.json', 'w', encoding='utf-8') as f:
        json.dump(datos_json, f, ensure_ascii=False, indent=4)
    
    os.makedirs("docs", exist_ok=True)
    with open('docs/data.json', 'w', encoding='utf-8') as f:
        json.dump(datos_json, f, ensure_ascii=False, indent=4)
    print("[+] Base generada exitosamente en docs/data.json")

if __name__ == "__main__":
    archivo = obtener_archivo_cafci()
    if archivo:
        procesar_etl(archivo)