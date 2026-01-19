import os
import google.generativeai as genai
from pydantic import BaseModel
from typing import Optional

# --- Configuración de la IA ---
# Asegúrate de que la Key exista, si no, usa una por defecto para pruebas o maneja el error
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# --- Estructura de datos para la respuesta de la IA ---
class AnalisisTicket(BaseModel):
    es_ticket_valido: bool
    categoria: str
    prioridad: str
    resumen: str
    id_ticket: Optional[str] = None

# --- Función 1: Analizar el problema ---
def analizar_ticket(mensaje_usuario: str):
    """
    Usa Gemini para entender si el correo es un problema real y extraer datos.
    """
    if not GOOGLE_API_KEY:
        print("❌ Error: No se encontró GOOGLE_API_KEY")
        return None

    try:
        # Usamos un modelo rápido y económico
        model = genai.GenerativeModel('gemini-1.5-flash',
            generation_config={
                "response_mime_type": "application/json", 
                "response_schema": AnalisisTicket
            }
        )

        prompt = f"""
        Actúa como un experto en soporte técnico nivel 2. Analiza este correo:
        "{mensaje_usuario}"

        Tu misión:
        1. Decidir si es un reporte de incidente real (es_ticket_valido). 
           - Si es spam, marketing o "gracias", es False.
        2. Categorizar (Ej: Hardware, Software, Acceso, Red, Facturación).
        3. Priorizar (Baja, Media, Alta, Crítica).
        4. Resumir el problema en menos de 10 palabras.
        5. Generar un ID sugerido (ej: TCK-8833).
        """

        response = model.generate_content(prompt)
        # Gemini con response_schema ya devuelve un objeto parseable, 
        # pero aquí lo devolvemos como objeto Python directo gracias a Pydantic
        # Nota: En versiones nuevas de la librería, response.parsed es el objeto.
        # Si da error, usaremos json.loads(response.text). 
        # Por simplicidad en Vercel, confiamos en el objeto instanciado:
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
        No prometas tiempos exactos, solo di que el equipo ya lo está revisando.
        Firma: "El Equipo de Soporte".
        """
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"⚠️ Error generando respuesta: {e}")
        return "Estimado usuario, hemos recibido su reporte y nuestro equipo técnico lo está revisando. Saludos."