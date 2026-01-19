import os
import json
import google.generativeai as genai
from pydantic import BaseModel

# --- Configuración de la IA ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# --- Estructura de datos (Para usar en main.py) ---
class AnalisisTicket(BaseModel):
    es_ticket_valido: bool
    categoria: str
    prioridad: str
    resumen: str
    id_ticket: str

# --- Función 1: Analizar el problema (Versión Manual) ---
def analizar_ticket(mensaje_usuario: str):
    """
    Usa Gemini para entender si el correo es un problema real y extraer datos.
    """
    if not GOOGLE_API_KEY:
        print("❌ Error: No se encontró GOOGLE_API_KEY")
        return None

    try:
        # SOLUCIÓN: Quitamos 'response_schema' para evitar el error "Unknown field"
        # Solo pedimos que responda en JSON.
        model = genai.GenerativeModel('gemini-1.5-flash',
            generation_config={"response_mime_type": "application/json"} 
        )

        prompt = f"""
        Actúa como un experto en soporte técnico. Analiza este correo:
        "{mensaje_usuario}"

        Tu misión es extraer estos datos en formato JSON exacto:
        {{
            "es_ticket_valido": true/false, (true si es un reporte real)
            "categoria":Str, (Ej: Hardware, Software, Acceso, Facturación)
            "prioridad": Str, (Baja, Media, Alta, Crítica)
            "resumen": Str, (Resumen en max 10 palabras)
            "id_ticket": Str (Genera un ID único ej: TCK-8833. Si no aplica, pon "N/A")
        }}
        """

        response = model.generate_content(prompt)
        
        # PROCESAMIENTO MANUAL (A prueba de errores)
        # Convertimos el texto JSON de la IA en un objeto Python nosotros mismos
        datos_dict = json.loads(response.text)
        
        # Lo convertimos al formato que espera main.py
        return AnalisisTicket(**datos_dict)

    except Exception as e:
        print(f"⚠️ Error al analizar ticket con IA: {e}")
        return None

# --- Función 2: Redactar respuesta ---
def generar_respuesta_cliente(cliente_nombre: str, categoria: str, prioridad: str):
    """
    Usa Gemini para escribir un correo amable confirmando el ticket.
    """
    if not GOOGLE_API_KEY:
        return "Hemos recibido su solicitud. Un técnico la revisará pronto."

    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
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