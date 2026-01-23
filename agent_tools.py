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

# Usamos una temperatura baja para precisión técnica, pero no cero para fluidez verbal
generation_config = {
  "temperature": 0.2, 
  "max_output_tokens": 1024,
}

# --- Estructura de datos ---
class AnalisisTicket(BaseModel):
    es_ticket_valido: bool
    categoria: str
    prioridad: str
    resumen: str
    id_ticket: str
    modulo_detectado: str
    datos_faltantes: str
    intencion: str 

# --- Función Auxiliar ---
def generar_id_ticket():
    fecha = datetime.datetime.now().strftime("%y%m%d")
    suffix = str(random.randint(100, 999))
    return f"TK-{fecha}-{suffix}"

# --- FUNCIÓN 1: EL AUDITOR ESTRICTO (Cerebro) ---
def analizar_ticket(mensaje_usuario: str):
    nuevo_id = generar_id_ticket()

    if not GOOGLE_API_KEY:
        return AnalisisTicket(es_ticket_valido=True, categoria="Error", prioridad="Alta", resumen="Falta API Key", id_ticket=nuevo_id, modulo_detectado="N/A", datos_faltantes="N/A", intencion="REPORTE")

    try:
        # Usamos gemini-pro (estable y compatible)
        model = genai.GenerativeModel('gemini-pro', generation_config=generation_config)

        prompt = f"""
        ROL: Eres un Auditor de Calidad de Soporte Técnico (Nivel 2).
        TAREA: Analizar si el reporte del cliente cumple los estándares para ser procesado.
        
        MENSAJE DEL CLIENTE: "{mensaje_usuario}"

        CRITERIOS DE ACEPTACIÓN (Checklist Obligatoria):
        1. [SISTEMA]: ¿Indica S.O. o plataforma?
        2. [MODULO]: ¿Indica qué parte del sistema falla (Ventas, Stock, Login)?
        3. [ERROR]: ¿Cita el mensaje de error o código específico?
        4. [PASOS]: ¿Describe qué estaba haciendo?
        5. [EVIDENCIA]: ¿Menciona adjuntos o capturas?

        REGLAS DE INTENCIÓN:
        - Si solo saluda o agradece ("Gracias", "Ok") -> intencion="SALUDO".
        - Si solo envía un archivo/foto -> intencion="APORTE".
        - Si describe un problema -> intencion="REPORTE".

        REGLAS DE SALIDA (JSON):
        - Si es REPORTE y falta ALGO de la checklist -> En 'datos_faltantes' lista EXPLICITAMENTE qué falta (ej: "Captura de pantalla y Pasos para reproducir").
        - Si el mensaje es muy breve (ej: "no anda") -> ASUME QUE FALTA TODO.
        
        Responde SOLO el JSON:
        {{
            "es_ticket_valido": true,
            "intencion": "REPORTE, SALUDO o APORTE",
            "categoria": "Software/Hardware/Red/Facturación",
            "prioridad": "Baja/Media/Alta",
            "modulo_detectado": "Nombre o 'General'",
            "resumen": "Resumen ejecutivo (max 10 palabras)",
            "datos_faltantes": "Lista detallada de faltantes o 'Ninguno'"
        }}
        """

        response = model.generate_content(prompt)
        match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if match:
            datos_dict = json.loads(match.group(0))
            datos_dict["id_ticket"] = nuevo_id
            return AnalisisTicket(**datos_dict)
        else:
            raise Exception("Error Formato JSON")

    except Exception as e:
        print(f"⚠️ Error IA Analisis: {e}")
        return AnalisisTicket(
            es_ticket_valido=True, categoria="General", prioridad="Media", resumen="Ticket Manual",
            id_ticket=nuevo_id, modulo_detectado="N/A", datos_faltantes="Revisión humana", intencion="REPORTE"
        )

# --- FUNCIÓN 2: EL AGENTE EXPERTO (La Voz Profesional) ---
def generar_respuesta_cliente(cliente_nombre: str, categoria: str, datos_faltantes: str, id_ticket: str, intencion: str, modulo: str):
    try:
        model = genai.GenerativeModel('gemini-pro', generation_config=generation_config)

        # --- ESTRATEGIA DE COMUNICACIÓN ---
        if intencion == "SALUDO":
            tarea = "Agradecer el contacto y cerrar el ticket formalmente."
        elif intencion == "APORTE":
            tarea = "Confirmar recepción de la evidencia y notificar que se agregó al expediente."
        else:
            # Es un REPORTE
            if "Ninguno" in datos_faltantes or "ninguno" in datos_faltantes:
                tarea = f"Confirmar que el reporte sobre '{modulo}' es completo. Informar escalamiento a Nivel 2. SLA: 4hs."
            else:
                tarea = f"""
                DETENER EL PROCESO Y SOLICITAR INFORMACIÓN.
                Debes explicar amablemente que para diagnosticar el problema en '{modulo}', necesitamos OBLIGATORIAMENTE:
                {datos_faltantes}.
                Usa una lista con viñetas (-).
                """

        # --- PROMPT ESTILO 'REWRITE.PY' ---
        prompt = f"""
        ACTÚA COMO: Agente Senior de Soporte Corporativo (Customer Success).
        IDIOMA: Español Formal y Profesional.
        TONO: Empático, Resolutivo, Ejecutivo.

        CONTEXTO:
        Cliente: {cliente_nombre}
        Ticket ID: {id_ticket}
        Categoría: {categoria}

        TAREA: Redactar correo de respuesta.
        OBJETIVO ESPECÍFICO: {tarea}

        ESTRUCTURA OBLIGATORIA DEL CORREO:
        1. Saludo cordial personalizado (Estimado {cliente_nombre}...)
        2. Confirmación del Ticket #{id_ticket}.
        3. CUERPO CENTRAL: Desarrolla el 'OBJETIVO ESPECÍFICO' de forma clara. Si pides datos, usa lista.
        4. Recordatorio: "Puede responder a este correo adjuntando imágenes o archivos."
        5. Cierre profesional (Atentamente, Equipo de Soporte).
        """
        
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Estimado {cliente_nombre}, hemos registrado su ticket #{id_ticket}. Un agente revisará su caso."