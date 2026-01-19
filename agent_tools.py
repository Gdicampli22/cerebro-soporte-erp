import os
import json
import re
import google.generativeai as genai
from pydantic import BaseModel

# --- Configuración de la IA ---
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

# --- Función 1: Analizar el problema (Con limpieza Regex) ---
def analizar_ticket(mensaje_usuario: str):
    """
    Usa Gemini Pro para analizar el ticket y limpia la respuesta con Regex.
    """
    if not GOOGLE_API_KEY:
        print("❌ Error: No se encontró GOOGLE_API_KEY")
        return None

    try:
        # Usamos 'gemini-pro' que es el modelo más compatible
        model = genai.GenerativeModel('gemini-3-flash-preview')

        prompt = f"""
        Actúa como sistema de soporte. Analiza este correo:
        "{mensaje_usuario}"

        Tu salida debe ser ÚNICAMENTE un JSON válido.
        Estructura obligatoria:
        {{
            "es_ticket_valido": true/false,
            "categoria": "Hardware/Software/Red/Otro",
            "prioridad": "Baja/Media/Alta/Critica",
            "resumen": "Resumen corto (max 10 palabras)",
            "id_ticket": "Genera ID único ej: TCK-8833"
        }}
        """

        response = model.generate_content(prompt)
        texto_crudo = response.text
        
        # --- EL BISTURÍ (Regex) ---
        # Busca texto entre llaves { ... } ignorando todo lo demás
        match = re.search(r'\{.*\}', texto_crudo, re.DOTALL)
        
        if match:
            json_str = match.group(0)
            datos_dict = json.loads(json_str)
            return AnalisisTicket(**datos_dict)
        else:
            print(f"⚠️ IA no devolvió JSON limpio. Recibido: {texto_crudo}")
            return None

    except Exception as e:
        print(f"⚠️ Error fatal en IA: {e}")
        return None

# --- Función 2: Redactar respuesta ---
def generar_respuesta_cliente(cliente_nombre: str, categoria: str, prioridad: str):
    """
    Usa Gemini Pro para escribir un correo de respuesta.
    """
    if not GOOGLE_API_KEY:
        return "Hemos recibido su solicitud. Un técnico la revisará pronto."

    try:
        model = genai.GenerativeModel('gemini-pro')
        
        prompt = f"""
        Escribe un correo muy breve (max 3 líneas) para el cliente "{cliente_nombre}".
        Confirma recepción del caso "{categoria}" con prioridad "{prioridad}".
        Firma: Soporte Técnico.
        """
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"⚠️ Error generando respuesta: {e}")
        return "Estimado usuario, hemos recibido su reporte. Saludos."