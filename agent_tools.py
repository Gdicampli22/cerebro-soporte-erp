import os
import json
import re
import google.generativeai as genai
from pydantic import BaseModel
import uuid

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
    Intenta usar Gemini 3. Si falla, activa el paracaídas para no dar Error 500.
    """
    # ID de respaldo por si todo falla
    backup_id = f"TCK-{str(uuid.uuid4())[:4].upper()}"

    if not GOOGLE_API_KEY:
        print("❌ Error: No se encontró GOOGLE_API_KEY")
        # Paracaídas 1: Sin API Key
        return AnalisisTicket(
            es_ticket_valido=True,
            categoria="Error Configuración",
            prioridad="Alta",
            resumen="Falta API Key",
            id_ticket=backup_id
        )

    try:
        # MODELO ELEGIDO POR EL USUARIO
        nombre_modelo = 'gemini-3-flash-preview'
        
        model = genai.GenerativeModel(nombre_modelo)

        prompt = f"""
        Actúa como soporte técnico. Analiza: "{mensaje_usuario}"
        Responde SOLO JSON válido:
        {{
            "es_ticket_valido": true,
            "categoria": "Soporte",
            "prioridad": "Media",
            "resumen": "Resumen del caso",
            "id_ticket": "Genera ID único"
        }}
        """

        response = model.generate_content(prompt)
        texto_crudo = response.text
        
        # Limpieza con Regex (Bisturí)
        match = re.search(r'\{.*\}', texto_crudo, re.DOTALL)
        
        if match:
            json_str = match.group(0)
            datos_dict = json.loads(json_str)
            return AnalisisTicket(**datos_dict)
        else:
            raise Exception(f"JSON no encontrado en respuesta: {texto_crudo}")

    except Exception as e:
        print(f"⚠️ FALLO LA IA ({nombre_modelo}): {e}")
        
        # --- PARACAÍDAS DE EMERGENCIA (EVITA EL ERROR 500) ---
        # Si la IA falla, devolvemos un ticket manual para que el sistema siga funcionando
        return AnalisisTicket(
            es_ticket_valido=True,
            categoria="Revisión Manual (Fallo IA)",
            prioridad="Media",
            resumen="Error al conectar con IA",
            id_ticket=backup_id
        )

# --- Función 2: Redactar respuesta ---
def generar_respuesta_cliente(cliente_nombre: str, categoria: str, prioridad: str):
    try:
        model = genai.GenerativeModel('gemini-3-flash-preview')
        prompt = f"Escribe respuesta corta soporte para {cliente_nombre} sobre {categoria}."
        response = model.generate_content(prompt)
        return response.text
    except Exception:
        return "Hemos recibido su reporte. Un agente lo revisará pronto."