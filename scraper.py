import pandas as pd
import json
import os
import requests
import io
import time
import re
import google.generativeai as genai
from datetime import datetime, timedelta

def analizar_con_gemini(df_res):
    # Intentamos obtener la API KEY
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "<p><i>Análisis IA no disponible (API Key no configurada).</i></p>"
    
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash') 
        
        # 1. Agrupamos los datos por Sociedad Depositaria (SD)
        df_sd = df_res.copy()
        # Calculamos el Fee Ponderado matemáticamente
        df_sd['Pond_SD'] = df_sd['Hon_SD'] * df_sd['Patrimonio']
        res_sd = df_sd.groupby('Sociedad_Depositaria').agg({'Patrimonio': 'sum', 'Pond_SD': 'sum'}).reset_index()
        # Evitamos divisiones por cero
        res_sd['Fee_Pond'] = (res_sd['Pond_SD'] / res_sd['Patrimonio']).fillna(0)
        
        # 2. Extraemos ÚNICAMENTE a nuestro Banco y a la competencia directa
        datos_competencia = ""
        for index, row in res_sd.iterrows():
            nombre = str(row['Sociedad_Depositaria']).upper()
            if "VALORES" in nombre or "COMAFI" in nombre or "INDUSTRIAL" in nombre:
                # Formateamos AUM a Billones para que la IA lo entienda fácil
                aum_billones = row['Patrimonio'] / 1e9 
                fee = row['Fee_Pond']
                datos_competencia += f"- {row['Sociedad_Depositaria']}: AUM ${aum_billones:.2f} Billones | Fee Promedio: {fee:.3f}%\n"
        
        # 3. EL PROMPT FORTALECIDO (Rol, Contexto y Tarea)
        prompt = f"""
        Actúa como un Director de Inteligencia Competitiva para la Mesa de Dinero del Banco Industrial (BIND). 
        A continuación, te presento los datos actualizados de cierre de hoy (Patrimonio bajo administración o AUM, y la tasa de honorarios Fee promedio ponderada) de nuestra entidad frente a nuestros dos principales competidores directos en el rol de Sociedad Depositaria:
        
        {datos_competencia}
        
        Tu tarea:
        Escribe un análisis competitivo muy profesional, contundente y al grano (máximo 2 párrafos cortos).
        1. Compara el posicionamiento de Banco Industrial frente a Banco de Valores y Banco Comafi en términos de volumen de mercado (AUM) y agresividad de precios (Fees).
        2. Identifica si nuestra estrategia de precios (nuestro Fee) está por encima o por debajo de la competencia directa y qué lectura estratégica o de captación de mercado se puede hacer de esto.
        
        IMPORTANTE: Devuelve tu respuesta ÚNICAMENTE con etiquetas HTML válidas (<p>, <b>, <ul>, <li>) para que se integre nativamente en nuestro Dashboard corporativo. NO uses bloques de código (```html).
        """
        
        # 4. Llamada a la IA
        respuesta = model.generate_content(prompt)
        texto_html = respuesta.text.replace("```html", "").replace("```", "").strip()
        return texto_html
        
    except Exception as e:
        print(f"[-] Error en Gemini: {e}")
        return "<p><i>El servicio de análisis competitivo de IA se encuentra temporalmente fuera de servicio.</i></p>"

def obtener_y_procesar_cafci():
    timestamp_actual = int(time.time() * 1000)
    URL_API_CAFCI = f"https://api.pub.cafci.org.ar/pb_get?d={timestamp_actual}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    print(f"[+] Conectando a la API de CAFCI...")
    try:
        respuesta = requests.get(URL_API_CAFCI, headers=headers, timeout=30)
        if respuesta.status_code == 200 and len(respuesta.content) > 5000:
            nombre_archivo_real = "Planilla_CAFCI.xlsx"
            if 'content-disposition' in respuesta.headers:
                cd = respuesta.headers['content-disposition']
                nombres = re.findall('filename="?([^";]+)"?', cd)
                if nombres: nombre_archivo_real = nombres[0]
            
            excel_memoria = io.BytesIO(respuesta.content)
            df = pd.read_excel(excel_memoria, skiprows=7, header=[0, 1])
            
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
            
            # --- AQUÍ INVOCAMOS A LA INTELIGENCIA ARTIFICIAL ---
            print("[+] Solicitando análisis a Gemini AI...")
            resumen_ia = analizar_con_gemini(df_res)
            
            hora_arg = datetime.now() - timedelta(hours=3)
            fecha_str = hora_arg.strftime("%d/%m/%Y %H:%M:%S")

            datos_json = {
                "fecha_actualizacion": fecha_str,
                "archivo_origen": nombre_archivo_real,
                "resumen_ia": resumen_ia, # <--- AGREGAMOS EL RESUMEN AL JSON
                "fondos": df_res.to_dict(orient='records')
            }

            os.makedirs("docs", exist_ok=True)
            with open('docs/data.json', 'w', encoding='utf-8') as f:
                json.dump(datos_json, f, ensure_ascii=False, indent=4)
            
            print(f"[+] Éxito total. Datos y Análisis IA inyectados.")
            return True
    except Exception as e:
        print(f"[-] Error Crítico: {e}")
        return False

if __name__ == "__main__":
    obtener_y_procesar_cafci()