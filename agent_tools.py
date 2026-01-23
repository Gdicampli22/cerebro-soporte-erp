import os
import json
import re
import google.generativeai as genai
from pydantic import BaseModel
import datetime
import random

# --- Configuración (Inspirada en rewrite.py) ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# Configuración para respuestas más consistentes y profesionales
generation_config = {
  "temperature": 0.4,           # Más bajo = más preciso y profesional
  "max_output_tokens": 1024,    # Permite respuestas bien desarrolladas
}

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
    # Ejemplo: TK-240123-X99
    fecha = datetime.datetime.now().strftime("%y%m%d")
    suffix = str(random.randint(100, 999))
    return f"TK-{fecha}-{suffix}"

# --- Función 1: Cerebro Analítico (Extrae datos para la DB) ---
def analizar_ticket(mensaje_usuario: str):
    nuevo_id = generar_id_ticket()

    if not GOOGLE_API_KEY:
        # Fallback de seguridad
        return AnalisisTicket(es_ticket_valido=True, categoria="Error Config", prioridad="Alta", resumen="Falta API Key", id_ticket=nuevo_id, datos_faltantes="N/A")

    try:
        # Usamos 1.5-flash porque es rápido y estable para sacar JSON
        model = genai.GenerativeModel('gemini-1.5-flash', generation_config=generation_config)

        prompt = f"""
        Actúa como un Analista de Soporte Técnico Senior (Nivel 2).
        
        TAREA:
        Analiza el siguiente reporte de incidente: "{mensaje_usuario}"
        
        OBJETIVO:
        1. Categorizar el problema (Software, Hardware, Acceso, Facturación).
        2. Determinar prioridad (Baja, Media, Alta, Crítica).
        3. Identificar QUÉ INFORMACIÓN FALTA para resolver el caso.
           - Si el usuario dice "no anda" y nada más -> Falta: "Captura de pantalla, mensaje de error exacto y pasos para reproducirlo".
           - Si el reporte es completo -> Falta: "Ninguno".
        
        FORMATO DE SALIDA (JSON PURO):
        {{
            "es_ticket_valido": true,
            "categoria": "Categoría detectada",
            "prioridad": "Prioridad asignada",
            "resumen": "Resumen técnico ejecutivo (max 10 palabras)",
            "datos_faltantes": "Lista de lo que falta o 'Ninguno'"
        }}
        """

        response = model.generate_content(prompt)
        
        # Limpieza quirúrgica del JSON
        match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if match:
            datos_dict = json.loads(match.group(0))
            datos_dict["id_ticket"] = nuevo_id # Inyectamos el ID generado
            return AnalisisTicket(**datos_dict)
        else:
            raise Exception("No se generó JSON válido")

    except Exception as e:
        print(f"⚠️ Error en análisis IA: {e}")
        return AnalisisTicket(
            es_ticket_valido=True,
            categoria="Soporte General",
            prioridad="Media",
            resumen="Ticket manual (Fallo Análisis)",
            id_ticket=nuevo_id,
            datos_faltantes="Revisión manual requerida"
        )

# --- Función 2: El Redactor Profesional (Lo que ve el cliente) ---
def generar_respuesta_cliente(cliente_nombre: str, categoria: str, datos_faltantes: str, id_ticket: str):
    """
    Genera una respuesta con estructura profesional: Saludo -> Confirmación -> Acción -> Cierre.
    Adaptado del estilo de 'rewrite.py'.
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash', generation_config=generation_config)
        
        # Definimos la instrucción precisa basada en si faltan datos o no
        if "Ninguno" in datos_faltantes or "ninguno" in datos_faltantes:
            enfoque = "Confirmar que el equipo técnico ya está revisando el caso. Dar tranquilidad."
        else:
            enfoque = f"Solicitar amablemente pero con urgencia la siguiente información faltante: {datos_faltantes}. Explicar que es necesaria para avanzar."

        prompt = f"""
        Actúa como un Agente Experto de Soporte al Cliente (Customer Success).
        
        CONTEXTO:
        Estás respondiendo automáticamente al cliente "{cliente_nombre}".
        Hemos creado el Ticket #{id_ticket} categorizado como "{categoria}".
        
        TAREA:
        Redacta una respuesta por correo electrónico.
        
        PAUTAS DE ESTILO (Importante):
        - Tono: Profesional, empático, resolutivo y seguro.
        - Idioma: Español neutro formal.
        - Estructura obligatoria:
          1. Saludo cordial personalizado.
          2. Confirmación de recepción del ticket y su ID.
          3. CUERPO DEL MENSAJE: {enfoque}
          4. Recordatorio: Mencionar que puede adjuntar imágenes o archivos respondiendo a este correo.
          5. Cierre formal (ej: "Atentamente, El Equipo de Soporte").
        
        IMPORTANTE: No uses marcadores de posición como [Nombre], usa los datos reales provistos.
        """
        
        response = model.generate_content(prompt)
        return response.text.strip()
    
    except Exception as e:
        # Fallback seguro pero profesional
        return f"""
        Estimado/a {cliente_nombre},
        
        Gracias por contactar a Soporte Técnico. Hemos recibido su solicitud y se ha generado el ticket #{id_ticket}.
        
        Nuestro equipo está analizando su caso. Si tiene información adicional o capturas de pantalla, por favor responda a este correo adjuntándolas.
        
        Atentamente,
        El Equipo de Soporte.
        """