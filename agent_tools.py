import os
import google.generativeai as genai
from pydantic import BaseModel
from typing import Optional

# Configuración de la IA
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

# Estructura de salida esperada (JSON)
class AnalisisTicket(BaseModel):
    es_ticket_valido: bool
    categoria: str
    prioridad: str
    resumen: str
    id_ticket: Optional[str] = None

def analizar_ticket(mensaje_usuario: str):
    """
    Analiza si el mensaje es un problema técnico y extrae datos clave.
    """
    model = genai.GenerativeModel('gemini-1.5-flash',
        generation_config={"response_mime_type": "application/json", "response_schema": AnalisisTicket}
    )

    prompt = f"""
    Eres un experto en soporte técnico de un ERP. Analiza el siguiente correo:
    "{mensaje_usuario}"

    1. Determina si es un reporte de problema real (es_ticket_valido).
       - Si es spam, publicidad o notificación automática, es False.
    2. Categoriza el problema (Ej: Facturación, Logística, Acceso, Impresoras, General).
    3. Asigna prioridad (Baja, Media, Alta, Crítica).
    4. Genera un resumen corto del problema (max 10 palabras).
    5. Genera un ID de ticket único (Ej: TCK-123456).
    """

    try:
        response = model.generate_content(prompt)
        return response.content  # Devuelve el objeto parseado por Pydantic automáticamente (o el texto JSON)
    except Exception as e:
        print(f"Error en IA: {e}")
        return None

def generar_respuesta_cliente(cliente_nombre: str, categoria: str, prioridad: str):
    """
    Redacta una respuesta formal y empática para el cliente.
    """
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    Redacta un correo de respuesta corto y formal para el cliente {cliente_nombre}.
    Confírmale que hemos recibido su reporte sobre "{categoria}" y que se le ha asignado prioridad "{prioridad}".
    Dile que un técnico lo revisará pronto. Firma como 'Soporte Técnico ERP'.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return "Hemos recibido su ticket y lo estamos procesando."