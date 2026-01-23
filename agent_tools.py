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

# Configuración precisa para evitar "alucinaciones"
generation_config = {
  "temperature": 0.2, # Muy bajo para ser extremadamente formal y preciso
  "max_output_tokens": 1024,
}

# --- Estructura de datos ---
class AnalisisTicket(BaseModel):
    es_ticket_valido: bool
    categoria: str
    prioridad: str
    resumen: str
    id_ticket: str
    datos_faltantes: str
    intencion: str  # REPORTE, APORTE, SALUDO

# --- Función Auxiliar ---
def generar_id_ticket():
    fecha = datetime.datetime.now().strftime("%y%m%d")
    suffix = str(random.randint(100, 999))
    return f"TK-{fecha}-{suffix}"

# --- Función 1: El Clasificador Estratégico ---
def analizar_ticket(mensaje_usuario: str):
    nuevo_id = generar_id_ticket()

    if not GOOGLE_API_KEY:
        # Fallback de seguridad
        return AnalisisTicket(
            es_ticket_valido=True, categoria="Error Config", prioridad="Alta", 
            resumen="Falta API Key", id_ticket=nuevo_id, datos_faltantes="N/A", intencion="REPORTE"
        )

    try:
        model = genai.GenerativeModel('gemini-1.5-flash', generation_config=generation_config)

        prompt = f"""
        Actúa como un Clasificador Senior de Mesa de Ayuda Corporativa.
        Analiza el siguiente mensaje entrante: "{mensaje_usuario}"

        TU MISIÓN:
        Clasificar la INTENCIÓN del usuario con precisión quirúrgica.

        REGLAS DE CLASIFICACIÓN (Campo 'intencion'):
        1. "SALUDO": Si el mensaje es SOLO un agradecimiento, confirmación de espera o cierre (ej: "Gracias", "Ok, aguardo", "Entendido").
        2. "APORTE": Si el mensaje SOLO contiene adjuntos, logs o respuestas a una pregunta previa sin reportar nada nuevo.
        3. "REPORTE": Si el usuario describe un problema, error, o hace una consulta técnica.

        REGLAS DE DATOS (Solo para REPORTE):
        - Si es SALUDO o APORTE -> datos_faltantes: "Ninguno".
        - Si es REPORTE -> Lista qué falta para resolverlo (Capturas, Logs, ID Cliente) o "Ninguno" si está completo.

        Salida JSON ESTRICTA:
        {{
            "es_ticket_valido": true,
            "categoria": "Software/Hardware/Facturación/Consulta/General",
            "prioridad": "Baja/Media/Alta",
            "resumen": "Resumen ejecutivo (max 8 palabras)",
            "datos_faltantes": "Lista o 'Ninguno'",
            "intencion": "REPORTE, APORTE o SALUDO"
        }}
        """

        response = model.generate_content(prompt)
        
        # Extracción segura de JSON
        match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if match:
            datos_dict = json.loads(match.group(0))
            datos_dict["id_ticket"] = nuevo_id
            return AnalisisTicket(**datos_dict)
        else:
            raise Exception("Formato JSON no válido")

    except Exception as e:
        print(f"⚠️ Error IA Analisis: {e}")
        return AnalisisTicket(
            es_ticket_valido=True, categoria="General", prioridad="Media", 
            resumen="Revisión Manual", id_ticket=nuevo_id, datos_faltantes="Ninguno", intencion="REPORTE"
        )

# --- Función 2: El Redactor Profesional ---
def generar_respuesta_cliente(cliente_nombre: str, categoria: str, datos_faltantes: str, id_ticket: str, intencion: str):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash', generation_config=generation_config)

        # Definimos la estrategia de comunicación según la intención
        if intencion == "SALUDO":
            contexto = "El cliente ha enviado un mensaje de agradecimiento o confirmación."
            accion = "Agradece la comunicación, confirma que el ticket se mantiene actualizado y cierra con un saludo cordial. Sé breve."
        
        elif intencion == "APORTE":
            contexto = "El cliente ha enviado información adicional o archivos adjuntos."
            accion = "Confirma explícitamente la recepción de la nueva información/archivos. Indica que han sido anexados al Ticket e informa que el equipo técnico los analizará a la brevedad."
        
        else: # REPORTE
            contexto = f"El cliente reporta un incidente de categoría: {categoria}."
            if "Ninguno" in datos_faltantes or "ninguno" in datos_faltantes:
                accion = "Informa que el reporte es completo y ha sido derivado inmediatamente a un Especialista de Nivel 2. Pide paciencia mientras se gestiona."
            else:
                accion = f"Explica que para avanzar con la solución, es INDISPENSABLE que responda adjuntando: {datos_faltantes}."

        prompt = f"""
        Actúa como un Ejecutivo de Atención al Cliente Corporativo.
        Estás redactando una respuesta oficial.

        DATOS:
        - Cliente: {cliente_nombre}
        - Ticket ID: {id_ticket}
        - Situación: {contexto}

        INSTRUCCIÓN:
        Redacta el cuerpo del correo siguiendo esta lógica: {accion}

        REGLAS DE ESTILO (NO NEGOCIABLES):
        1. Tono: Formal, Empático, Ejecutivo y Resolutivo.
        2. Estructura: 
           - Saludo formal (Estimado/a...).
           - Referencia al Ticket #{id_ticket}.
           - Mensaje central (La Acción definida arriba).
           - Cierre profesional (Atentamente, [Nombre de Empresa/Soporte]).
        3. NO inventes nombres de agentes. Firma como "Equipo de Soporte".
        4. Idioma: Español Neutro.
        """
        
        response = model.generate_content(prompt)
        return response.text.strip()
    
    except Exception:
        return f"Estimado cliente, hemos actualizado la información de su ticket #{id_ticket}. Quedamos a su disposición."