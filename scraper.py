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
    # Intentamos obtener la API KEY (Si corres local sin clave, no se rompe)
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "<p><i>Análisis IA no disponible (API Key no configurada).</i></p>"
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash') # Modelo rápido y económico
        
        # 1. Cálculos matemáticos del Top 5 Fees Ponderados
        df_sg = df_res[df_res['Hon_SG'] > 0].copy()
        df_sg['Pond'] = df_sg['Hon_SG'] * df_sg['Patrimonio']
        agrupado = df_sg.groupby('Sociedad_Gerente').agg({'Patrimonio': 'sum', 'Pond': 'sum'})
        agrupado['Fee_Ponderado'] = agrupado['Pond'] / agrupado['Patrimonio']
        top5 = agrupado.sort_values('Fee_Ponderado', ascending=False).head(5)
        
        # 2. Preparamos los datos para dárselos a Gemini
        datos_prompt = ""
        for sg, row in top5.iterrows():
            datos_prompt += f"- {sg}: Fee {row['Fee_Ponderado']:.2f}%, AUM: ${row['Patrimonio']/1e6:.1f}M\n"
        
        # 3. El Prompt (Instrucciones precisas)
        prompt = f"""
        Actúa como un experto analista de mesas de dinero (Treasury). 
        Estas son las 5 Sociedades Gerentes con las tasas de honorarios (fees) ponderadas más altas del mercado hoy:
        
        {datos_prompt}
        
        Escribe un breve y muy profesional resumen (máximo 2 párrafos cortos) analizando qué significa esta estructura de precios para la industria. 
        Menciona la relación entre el Fee cobrado y el volumen patrimonial (AUM).
        IMPORTANTE: Devuelve tu respuesta ÚNICAMENTE con etiquetas HTML válidas (<p>, <b>, <ul>, <li>). NO uses bloques de código (```html).
        """
        
        respuesta = model.generate_content(prompt)
        texto_html = respuesta.text.replace("```html", "").replace("```", "").strip()
        return texto_html
        
    except Exception as e:
        print(f"[-] Error en Gemini: {e}")
        return "<p><i>El servicio de análisis IA se encuentra temporalmente fuera de servicio.</i></p>"

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