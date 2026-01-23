import os
import json
import re
import google.generativeai as genai
from pydantic import BaseModel
import datetime
import random

# --- Configuración ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# Temperatura 0 para máxima precisión y cero creatividad inventada
generation_config = {
  "temperature": 0.0, 
  "max_output_tokens": 1024,
}

# --- Estructura de datos ---
class AnalisisTicket(BaseModel):
    es_ticket_valido: bool
    categoria: str
    prioridad: str
    resumen: str
    id_ticket: str
    modulo_detectado: str # Nuevo: Ej. Ventas, Contabilidad
    datos_faltantes: str
    intencion: str 

# --- Función Auxiliar ---
def generar_id_ticket():
    fecha = datetime.datetime.now().strftime("%y%m%d")
    suffix = str(random.randint(100, 999))
    return f"TK-{fecha}-{suffix}"

# --- Función 1: El Auditor de Calidad ---
def analizar_ticket(mensaje_usuario: str):
    nuevo_id = generar_id_ticket()

    if not GOOGLE_API_KEY:
        return AnalisisTicket(
            es_ticket_valido=True, categoria="Error", prioridad="Alta", resumen="Falta API Key", 
            id_ticket=nuevo_id, modulo_detectado="N/A", datos_faltantes="N/A", intencion="REPORTE"
        )

    try:
        model = genai.GenerativeModel('gemini-1.5-flash', generation_config=generation_config)

        prompt = f"""
        Actúa como un Auditor de Soporte Técnico (Nivel 2).
        Analiza el siguiente reporte: "{mensaje_usuario}"

        TU OBJETIVO:
        Verificar si el reporte cumple con los 5 REQUISITOS OBLIGATORIOS para ser gestionado.

        LISTA DE VERIFICACIÓN (CHECKLIST):
        1. [SISTEMA]: ¿Menciona el sistema operativo o navegador?
        2. [MODULO]: ¿Menciona el módulo afectado (ej: Ventas, Stock, Login)?
        3. [ERROR]: ¿Provee el mensaje de error textual o código?
        4. [DESCRIPCION]: ¿Explica qué paso estaba realizando antes del fallo?
        5. [EVIDENCIA]: ¿Menciona haber adjuntado capturas, logs o fotos?

        INSTRUCCIONES:
        - Si la intención es "SALUDO" (Gracias, Ok) o "APORTE" (Solo envío foto), ignora la checklist.
        - Si es "REPORTE", verifica qué falta.

        SALIDA JSON OBLIGATORIA:
        {{
            "es_ticket_valido": true,
            "intencion": "REPORTE, SALUDO o APORTE",
            "categoria": "Software/Hardware/Red/Facturación",
            "prioridad": "Baja/Media/Alta",
            "modulo_detectado": "Nombre del módulo o 'No especificado'",
            "resumen": "Resumen técnico (max 10 palabras)",
            "datos_faltantes": "Lista TEXTUAL de lo que falta de la checklist (ej: 'Módulo afectado y Captura de pantalla') o 'Ninguno' si tiene todo."
        }}
        """

        response = model.generate_content(prompt)
        
        match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if match:
            datos_dict = json.loads(match.group(0))
            datos_dict["id_ticket"] = nuevo_id
            return AnalisisTicket(**datos_dict)
        else:
            raise Exception("Error formato JSON")

    except Exception as e:
        print(f"⚠️ Error IA: {e}")
        return AnalisisTicket(
            es_ticket_valido=True, categoria="General", prioridad="Media", resumen="Manual",
            id_ticket=nuevo_id, modulo_detectado="N/A", datos_faltantes="Revisión humana", intencion="REPORTE"
        )

# --- Función 2: El Gestor de Casos (Respuesta) ---
def generar_respuesta_cliente(cliente_nombre: str, categoria: str, datos_faltantes: str, id_ticket: str, intencion: str, modulo: str):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash', generation_config=generation_config)

        # Lógica estricta de gestión
        if intencion == "SALUDO":
            objetivo = "Cerrar la interacción cortésmente."
        elif intencion == "APORTE":
            objetivo = "Confirmar recepción de evidencia y anexar al legajo."
        else:
            # Es un REPORTE
            if "Ninguno" in datos_faltantes or "ninguno" in datos_faltantes:
                objetivo = f"INFORMAR GESTIÓN: Confirmar que el reporte sobre el módulo '{modulo}' está completo. Indicar que se ha escalado al equipo de Desarrollo/Infraestructura para resolución inmediata."
            else:
                objetivo = f"SOLICITAR INFORMACIÓN: Detener la gestión. Explicar profesionalmente que NO se puede proceder sin los siguientes datos faltantes: {datos_faltantes}. Pedirlos en forma de lista."

        prompt = f"""
        Actúa como Gerente de Mesa de Ayuda Corporativa.
        Redacta un correo para el cliente: {cliente_nombre}.
        Ticket ID: {id_ticket}.

        OBJETIVO DEL CORREO: {objetivo}

        ESTRUCTURA EXIGIDA:
        1. Saludo formal.
        2. Referencia clara al estado del Ticket #{id_ticket}.
        3. CUERPO:
           - Si faltan datos: Pídelos usando viñetas (bullets) para que sea claro.
           - Si está completo: Confirma tiempos estimados de respuesta (SLA estándar).
        4. Cierre formal ("Atentamente, Equipo de Soporte").

        TONO: Profesional, técnico pero accesible, resolutivo.
        """
        
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception:
        return f"Ticket #{id_ticket} actualizado. Por favor verifique si necesitamos más información."