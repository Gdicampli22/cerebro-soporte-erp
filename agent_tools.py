import os
import google.generativeai as genai
from pydantic import BaseModel

# --- Configuración de la IA ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# --- Estructura de datos SIMPLIFICADA (Sin opcionales ni defaults) ---
class AnalisisTicket(BaseModel):
    es_ticket_valido: bool
    categoria: str
    prioridad: str
    resumen: str
    id_ticket: str  # Quitamos el Optional y el = None para evitar el error de schema

# --- Función 1: Analizar el problema ---
def analizar_ticket(mensaje_usuario: str):
    """
    Usa Gemini para entender si el correo es un problema real y extraer datos.
    """
    if not GOOGLE_API_KEY:
        print("❌ Error: No se encontró GOOGLE_API_KEY")
        return None

    try:
        model = genai.GenerativeModel('gemini-1.5-flash',
            generation_config={
                "response_mime_type": "application/json", 
                "response_schema": AnalisisTicket
            }
        )

        prompt = f"""
        Actúa como un experto en soporte técnico. Analiza este correo:
        "{mensaje_usuario}"

        Tu misión es extraer estos datos en formato JSON exacto:
        1. es_ticket_valido: true si es un reporte real, false si es spam/marketing.
        2. categoria: (Ej: Hardware, Software, Acceso, Facturación).
        3. prioridad: (Baja, Media, Alta, Crítica).
        4. resumen: Resumen del problema en max 10 palabras.
        5. id_ticket: Genera un ID único (Ej: TCK-8833). Si no es válido, pon "N/A".
        """

        response = model.generate_content(prompt)
        
        # Devolvemos el texto JSON directamente para que Pydantic lo procese en main.py
        # o el objeto instanciado si la librería lo soporta nativamente.
        return response.content

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