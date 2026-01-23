import os
import json
import re
import google.generativeai as genai
from pydantic import BaseModel
import datetime
import random

# --- Configuración ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# Configuración estándar (Temperatura baja para precisión)
generation_config = {
  "temperature": 0.3,
  "max_output_tokens": 1024,
}

class AnalisisTicket(BaseModel):
    es_ticket_valido: bool
    categoria: str
    prioridad: str
    resumen: str
    id_ticket: str
    modulo_detectado: str
    datos_faltantes: str
    intencion: str 
    razonamiento_ia: str

def generar_id_ticket():
    fecha = datetime.datetime.now().strftime("%y%m%d")
    suffix = str(random.randint(100, 999))
    return f"TK-{fecha}-{suffix}"

# --- NUEVA FUNCIÓN: LIMPIADOR DE JSON ---
def limpiar_json(texto_sucio):
    """
    Elimina markdown (```json ... ```) y busca el primer '{' y el último '}'
    para extraer solo el objeto JSON válido.
    """
    try:
        # 1. Quitar bloques de código markdown
        texto_limpio = re.sub(r"```json\s*", "", texto_sucio)
        texto_limpio = re.sub(r"```", "", texto_limpio)
        
        # 2. Buscar dónde empieza y termina el JSON real
        inicio = texto_limpio.find('{')
        fin = texto_limpio.rfind('}') + 1
        
        if inicio != -1 and fin != -1:
            return texto_limpio[inicio:fin]
        return texto_sucio # Si no encuentra llaves, devuelve original (y fallará luego)
    except:
        return texto_sucio

# --- FUNCIÓN 1: EL DIAGNOSTICADOR (Cerebro) ---
def analizar_ticket(mensaje_usuario: str):
    nuevo_id = generar_id_ticket()

    if not GOOGLE_API_KEY:
        return AnalisisTicket(es_ticket_valido=True, categoria="Error", prioridad="Alta", resumen="Falta API Key", id_ticket=nuevo_id, modulo_detectado="N/A", datos_faltantes="N/A", intencion="REPORTE", razonamiento_ia="Sin API")

    # Intentamos con gemini-1.5-flash, si falla, gemini-pro
    modelos = ['gemini-3-flash-preview', 'gemini-pro']
    
    for nombre_modelo in modelos:
        try:
            model = genai.GenerativeModel(nombre_modelo, generation_config=generation_config)

            prompt = f"""
            ACTÚA COMO: Ingeniero de Soporte Experto (Nivel 3).
            OBJETIVO: Diagnosticar qué información falta.

            REPORTE USUARIO: "{mensaje_usuario}"

            INSTRUCCIONES:
            1. Detecta INTENCIÓN: SALUDO (Gracias/Hola), APORTE (Envío archivo), REPORTE (Problema).
            2. Si es REPORTE:
               - NO uses una checklist fija. PIENSA qué se necesita para ESE problema específico.
               - Ej: "No imprime" -> Pide modelo de impresora. "Lento" -> Pide si es una sola PC.
            3. Genera la lista 'datos_faltantes' con preguntas específicas.

            RESPONDE SOLO EL JSON (Sin markdown):
            {{
                "es_ticket_valido": true,
                "intencion": "REPORTE, SALUDO o APORTE",
                "categoria": "Software/Hardware/Red/Consulta",
                "prioridad": "Baja/Media/Alta",
                "modulo_detectado": "Nombre o 'General'",
                "resumen": "Resumen técnico corto",
                "razonamiento_ia": "Por qué pides esto",
                "datos_faltantes": "Lista de preguntas o 'Ninguno'"
            }}
            """

            response = model.generate_content(prompt)
            
            # --- AQUÍ ESTÁ LA MAGIA DE LA CORRECCIÓN ---
            texto_limpio = limpiar_json(response.text)
            datos_dict = json.loads(texto_limpio)
            
            datos_dict["id_ticket"] = nuevo_id
            if "razonamiento_ia" not in datos_dict: datos_dict["razonamiento_ia"] = "IA"
            
            return AnalisisTicket(**datos_dict)

        except Exception as e:
            print(f"⚠️ Falló {nombre_modelo}: {e}")
            continue # Prueba el siguiente modelo

    # Fallback final si todo rompe
    return AnalisisTicket(
        es_ticket_valido=True, categoria="Soporte", prioridad="Media", resumen="Error Análisis",
        id_ticket=nuevo_id, modulo_detectado="N/A", datos_faltantes="Ninguno", intencion="REPORTE", razonamiento_ia="Fallo total"
    )

# --- FUNCIÓN 2: EL AGENTE (Voz) ---
def generar_respuesta_cliente(cliente_nombre: str, categoria: str, datos_faltantes: str, id_ticket: str, intencion: str, modulo: str):
    modelos = ['gemini-1.5-flash', 'gemini-pro']
    
    for nombre_modelo in modelos:
        try:
            model = genai.GenerativeModel(nombre_modelo, generation_config=generation_config)

            if intencion == "SALUDO":
                instruccion = "Agradece y cierra el caso formalmente."
            elif intencion == "APORTE":
                instruccion = "Confirma recepción y anexo al expediente."
            else:
                if "Ninguno" in datos_faltantes or "ninguno" in datos_faltantes:
                    instruccion = f"Confirma que el reporte es completo y se derivó a Nivel 2."
                else:
                    instruccion = f"""
                    TU OBJETIVO ES CONSEGUIR ESTOS DATOS FALTANTES:
                    {datos_faltantes}
                    
                    Explica al cliente por qué son necesarios para resolver su problema de '{categoria}'.
                    Sé amable pero técnico. Usa viñetas.
                    """

            prompt = f"""
            Redacta un correo de soporte PROFESIONAL.
            Cliente: {cliente_nombre}
            Ticket: {id_ticket}
            
            INSTRUCCIÓN: {instruccion}

            ESTILO:
            - Saludo formal.
            - Cuerpo claro y directo.
            - Cierre profesional.
            """
            
            response = model.generate_content(prompt)
            return response.text.strip()
        
        except Exception:
            continue
            
    return f"Estimado {cliente_nombre}, ticket #{id_ticket} recibido."