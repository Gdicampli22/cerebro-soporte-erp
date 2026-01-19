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
    Usa Gemini 3 para entender si el correo es un problema real y extraer datos.
    """
    if not GOOGLE_API_KEY:
        print("❌ Error: No se encontró GOOGLE_API_KEY")
        return None

    try:
        # ✅ ACTUALIZADO: Usamos el modelo que tú confirmaste
        nombre_modelo = 'gemini-3-flash-preview'
        
        # Usamos modo JSON manual para máxima compatibilidad
        model = genai.GenerativeModel(nombre_modelo,
            generation_config={"response_mime_type": "application/json"} 
        )

        prompt = f"""
        Actúa como un experto en soporte técnico. Analiza este correo:
        "{mensaje_usuario}"

        Tu misión es extraer estos datos en formato JSON exacto:
        {{
            "es_ticket_valido": true/false,
            "categoria": Str (Ej: Hardware, Software, Acceso, Facturación),
            "prioridad": Str (Baja, Media, Alta, Crítica),
            "resumen": Str (max 10 palabras),
            "id_ticket": Str (Genera un ID único ej: TCK-8833)
        }}
        """

        response = model.generate_content(prompt)
        
        # Procesamiento manual del JSON
        datos_dict = json.loads(response.text)
        return AnalisisTicket(**datos_dict)

    except Exception as e:
        print(f"⚠️ Error al analizar ticket con IA ({nombre_modelo}): {e}")
        return None

# --- Función 2: Redactar respuesta ---
def generar_respuesta_cliente(cliente_nombre: str, categoria: str, prioridad: str):
    """
    Usa Gemini para escribir un correo amable.
    """
    if not GOOGLE_API_KEY:
        return "Hemos recibido su solicitud. Un técnico la revisará pronto."

    try:
        # Usamos el mismo modelo potente para la respuesta
        model = genai.GenerativeModel('gemini-3-flash-preview')
        
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