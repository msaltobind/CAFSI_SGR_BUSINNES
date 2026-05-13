import pandas as pd
import json
import os
import requests
import io
import time
import re
from datetime import datetime, timedelta

def obtener_y_procesar_cafci():
    timestamp_actual = int(time.time() * 1000)
    URL_API_CAFCI = f"https://api.pub.cafci.org.ar/pb_get?d={timestamp_actual}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    print(f"[+] Conectando a la API de CAFCI...")
    
    try:
        respuesta = requests.get(URL_API_CAFCI, headers=headers, timeout=30)
        
        if respuesta.status_code == 200 and len(respuesta.content) > 5000:
            
            # --- MAGIA PARA OBTENER EL NOMBRE REAL DEL ARCHIVO ---
            nombre_archivo_real = "Planilla_CAFCI.xlsx" # Nombre por defecto si falla
            if 'content-disposition' in respuesta.headers:
                cd = respuesta.headers['content-disposition']
                nombres = re.findall('filename="?([^";]+)"?', cd)
                if nombres:
                    nombre_archivo_real = nombres[0]
            
            print(f"[+] Archivo detectado desde el servidor: {nombre_archivo_real}")
            
            # 2. Procesamiento en memoria
            excel_memoria = io.BytesIO(respuesta.content)
            df = pd.read_excel(excel_memoria, skiprows=7, header=[0, 1])
            
            # --- ETL ---
            nuevas_cols = []
            for p, s in df.columns:
                col_name = str(p).strip() if "Unnamed" in str(s) else f"{p}_{s}".strip()
                nuevas_cols.append(col_name)
            df.columns = nuevas_cols

            col_fondo = next(c for c in df.columns if 'Fondo' in c and 'Moneda' not in c)
            col_sg = next(c for c in df.columns if 'Sociedad Gerente' in c)
            col_sd = next(c for c in df.columns if 'Sociedad Depositaria' in c)
            col_patrimonio = next(c for c in df.columns if 'Patrimonio_Actual' in c or 'Patrimonio' in c)

            df_res = df[[col_fondo, col_sg, col_sd, col_patrimonio, 'Honorarios Adm. SG', 'Honorarios Adm. SD']].copy()
            df_res.columns = ['Fondo', 'Sociedad_Gerente', 'Sociedad_Depositaria', 'Patrimonio', 'Hon_SG', 'Hon_SD']
            df_res = df_res.dropna(subset=['Fondo', 'Patrimonio'])
            df_res['Patrimonio'] = pd.to_numeric(df_res['Patrimonio'], errors='coerce').fillna(0)
            
            # 3. METADATOS DE LA CORRIDA
            hora_arg = datetime.now() - timedelta(hours=3)
            fecha_str = hora_arg.strftime("%d/%m/%Y %H:%M:%S")

            datos_json = {
                "fecha_actualizacion": fecha_str,
                "archivo_origen": nombre_archivo_real, # <--- Aquí inyectamos el nombre oficial
                "fondos": df_res.to_dict(orient='records')
            }

            # 4. Guardar JSON para Producción
            os.makedirs("docs", exist_ok=True)
            with open('docs/data.json', 'w', encoding='utf-8') as f:
                json.dump(datos_json, f, ensure_ascii=False, indent=4)
            
            print(f"[+] Éxito: {nombre_archivo_real} procesado a las {fecha_str} HS")
            return True
        else:
            print("[-] Error: CAFCI no devolvió datos válidos.")
            return False
            
    except Exception as e:
        print(f"[-] Error Crítico: {e}")
        return False

if __name__ == "__main__":
    obtener_y_procesar_cafci()