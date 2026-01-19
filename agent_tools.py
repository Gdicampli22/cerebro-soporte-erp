import os
import json
import re
import google.generativeai as genai
from pydantic import BaseModel
import uuid

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

# --- Función 1: Analizar el problema ---
def analizar_ticket(mensaje_usuario: str):
    """
    Analiza el ticket usando Gemini 1.5 Flash (Rápido y con alto límite).
    Incluye protección contra fallos para no romper el servidor.
    """
    # ID de respaldo por si ocurre un error fatal
    backup_id = f"TCK-{str(uuid.uuid4())[:4].upper()}"

    # 1. Verificación de API Key
    if not GOOGLE_API_KEY:
        print("❌ Error: Falta API Key")
        return AnalisisTicket(
            es_ticket_valido=True, 
            categoria="Error Configuración", 
            prioridad="Alta", 
            resumen="Falta API Key en Vercel", 
            id_ticket=backup_id
        )

    try:
        # 2. Configuración del Modelo (El más rápido y estable)
        nombre_modelo = 'gemini-1.5-flash'
        model = genai.GenerativeModel(nombre_modelo)

        prompt = f"""
        Actúa como soporte técnico nivel 1. Analiza este reporte:
        "{mensaje_usuario}"

        Tu tarea: Extraer datos en formato JSON.
        Formato OBLIGATORIO:
        {{
            "es_ticket_valido": true,
            "categoria": "Clasifica el problema (Hardware, Software, Acceso, etc)",
            "prioridad": "Baja, Media o Alta",
            "resumen": "Resumen técnico muy breve",
            "id_ticket": "Genera un ID (ej: TCK-5599)"
        }}
        """

        # 3. Llamada a la IA
        response = model.generate_content(prompt)
        
        # 4. Limpieza Quirúrgica (Regex) - Extrae solo el JSON
        match = re.search(r'\{.*\}', response.text, re.DOTALL)
        
        if match:
            json_limpio = match.group(0)
            datos_dict = json.loads(json_limpio)
            return AnalisisTicket(**datos_dict)
        else:
            raise Exception("La IA respondió texto pero no JSON válido.")

    except Exception as e:
        print(f"⚠️ ALERTA: Falló la IA ({e}). Usando modo respaldo.")
        
        # 5. PARACAÍDAS DE EMERGENCIA
        # Si algo falla (límite de API, modelo caído, etc), devolvemos esto
        # para que Make reciba un 200 OK y el correo se envíe igual.
        return AnalisisTicket(
            es_ticket_valido=True,
            categoria="Soporte General (Fallo IA)",
            prioridad="Media",
            resumen="Ticket generado automáticamente (IA ocupada)",
            id_ticket=backup_id
        )

# --- Función 2: Redactar respuesta ---
def generar_respuesta_cliente(cliente_nombre: str, categoria: str, prioridad: str):
    try:
        # Usamos el mismo modelo rápido
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
        Redacta un correo muy corto (máximo 2 frases) para el cliente {cliente_nombre}.
        Confirma que recibimos su ticket de tipo {categoria}.
        Firma: El Equipo de Soporte.
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception:
        return "Gracias por contactarnos. Su ticket ha sido registrado y un técnico lo revisará pronto."