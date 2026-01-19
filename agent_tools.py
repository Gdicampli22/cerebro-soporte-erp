import os
import json
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

# --- Función 1: Analizar el problema ---
def analizar_ticket(mensaje_usuario: str):
    """
    Usa Gemini Pro (Estable) para analizar el ticket.
    """
    if not GOOGLE_API_KEY:
        print("❌ Error: No se encontró GOOGLE_API_KEY")
        return None

    try:
        # CAMBIO DEFINITIVO: Usamos 'gemini-pro'
        # Este nombre es universal y funciona con todas las versiones de la librería.
        nombre_modelo = 'gemini-pro'
        
        model = genai.GenerativeModel(nombre_modelo)

        prompt = f"""
        Actúa como un experto en soporte técnico. Analiza este correo:
        "{mensaje_usuario}"

        Responde ÚNICAMENTE con un objeto JSON válido (sin markdown, sin ```json).
        El JSON debe tener esta estructura exacta:
        {{
            "es_ticket_valido": true/false,
            "categoria": "Hardware/Software/Acceso/etc",
            "prioridad": "Baja/Media/Alta/Critica",
            "resumen": "Resumen corto",
            "id_ticket": "Genera un ID (ej: TCK-9922)"
        }}
        """

        response = model.generate_content(prompt)
        
        # Limpieza de seguridad por si la IA pone comillas raras o markdown
        texto_limpio = response.text.replace("```json", "").replace("```", "").strip()
        
        # Procesamiento manual
        datos_dict = json.loads(texto_limpio)
        return AnalisisTicket(**datos_dict)

    except Exception as e:
        print(f"⚠️ Error al analizar ticket con IA ({nombre_modelo}): {e}")
        return None

# --- Función 2: Redactar respuesta ---
def generar_respuesta_cliente(cliente_nombre: str, categoria: str, prioridad: str):
    """
    Usa Gemini Pro para escribir un correo amable.
    """
    if not GOOGLE_API_KEY:
        return "Hemos recibido su solicitud. Un técnico la revisará pronto."

    try:
        model = genai.GenerativeModel('gemini-pro')
        
        prompt = f"""
        Escribe un correo de respuesta muy breve y profesional para el cliente "{cliente_nombre}".
        Confirma que recibimos su reporte sobre "{categoria}".
        Infórmale que ha sido clasificado con prioridad "{prioridad}".
        No prometas tiempos exactos. Firma: "Soporte Técnico".
        """
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"⚠️ Error generando respuesta: {e}")
        return "Estimado usuario, hemos recibido su reporte. Saludos."