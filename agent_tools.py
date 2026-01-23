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

# --- Estructura de datos ---
class AnalisisTicket(BaseModel):
    es_ticket_valido: bool
    categoria: str
    prioridad: str
    resumen: str
    id_ticket: str
    datos_faltantes: str

# --- Función Auxiliar: Generar ID Profesional ---
def generar_id_ticket():
    fecha = datetime.datetime.now().strftime("%y%m%d")
    suffix = str(random.randint(100, 999))
    return f"TK-{fecha}-{suffix}"

# --- Función 1: Analizar el problema ---
def analizar_ticket(mensaje_usuario: str):
    nuevo_id = generar_id_ticket()

    if not GOOGLE_API_KEY:
        return AnalisisTicket(es_ticket_valido=True, categoria="Error Config", prioridad="Alta", resumen="Falta API Key", id_ticket=nuevo_id, datos_faltantes="N/A")

    try:
        nombre_modelo = 'gemini-1.5-flash'
        model = genai.GenerativeModel(nombre_modelo)

        prompt = f"""
        Actúa como soporte técnico Nivel 2. Analiza: "{mensaje_usuario}"
        Detecta qué falta para resolver el caso (ej: capturas, logs, nro factura).
        Si está todo bien, pon "Ninguno".
        
        Responde SOLO JSON:
        {{
            "es_ticket_valido": true,
            "categoria": "Hardware/Software/Red/Consulta",
            "prioridad": "Baja/Media/Alta",
            "resumen": "Resumen técnico corto",
            "datos_faltantes": "Lo que falta o 'Ninguno'"
        }}
        """

        response = model.generate_content(prompt)
        match = re.search(r'\{.*\}', response.text, re.DOTALL)
        
        if match:
            datos_dict = json.loads(match.group(0))
            datos_dict["id_ticket"] = nuevo_id
            return AnalisisTicket(**datos_dict)
        else:
            raise Exception("JSON no encontrado")

    except Exception as e:
        print(f"⚠️ Fallo IA: {e}")
        return AnalisisTicket(
            es_ticket_valido=True,
            categoria="Soporte General",
            prioridad="Media",
            resumen="Ticket manual (Error IA)",
            id_ticket=nuevo_id,
            datos_faltantes="Revisión manual"
        )

# --- Función 2: Redactar respuesta ---
def generar_respuesta_cliente(cliente_nombre: str, categoria: str, datos_faltantes: str, id_ticket: str):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        if "Ninguno" in datos_faltantes or "ninguno" in datos_faltantes:
            accion = "Su caso está siendo revisado."
        else:
            accion = f"Por favor responda adjuntando: {datos_faltantes}."

        prompt = f"""
        Redacta correo soporte para {cliente_nombre}.
        Ticket: {id_ticket} ({categoria}).
        Mensaje clave: "{accion}".
        Menciona que puede adjuntar archivos (Imágenes, PDF) en su respuesta.
        Máximo 3 líneas.
        """
        response = model.generate_content(prompt)
        return response.text
    except:
        return f"Ticket {id_ticket} registrado. {accion}"