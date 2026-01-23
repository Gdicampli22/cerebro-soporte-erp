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

# Temperatura baja para evitar creatividad innecesaria
generation_config = {
  "temperature": 0.0, 
  "max_output_tokens": 1024,
}

class AnalisisTicket(BaseModel):
    es_ticket_valido: bool
    categoria: str
    prioridad: str
    resumen: str
    id_ticket: str
    modulo_detectado: str
    datos_faltantes: str
    intencion: str 

def generar_id_ticket():
    fecha = datetime.datetime.now().strftime("%y%m%d")
    suffix = str(random.randint(100, 999))
    return f"TK-{fecha}-{suffix}"

# --- FUNCIÓN 1: EL AUDITOR ESTRICTO ---
def analizar_ticket(mensaje_usuario: str):
    nuevo_id = generar_id_ticket()

    if not GOOGLE_API_KEY:
        return AnalisisTicket(es_ticket_valido=True, categoria="Error", prioridad="Alta", resumen="Falta API Key", id_ticket=nuevo_id, modulo_detectado="N/A", datos_faltantes="N/A", intencion="REPORTE")

    try:
        # Usamos gemini-pro que ya confirmamos que funciona
        model = genai.GenerativeModel('gemini-3-flash-preview', generation_config=generation_config)

        prompt = f"""
        ERES UN AUDITOR DE SOPORTE TÉCNICO ESTRICTO.
        Analiza este reporte: "{mensaje_usuario}"

        TU ÚNICA TAREA ES VALIDAR SI ESTÁN PRESENTES ESTOS 5 DATOS OBLIGATORIOS:
        1. SISTEMA OPERATIVO (Windows, Web, App)
        2. MÓDULO (Ventas, Stock, Contabilidad, etc)
        3. MENSAJE DE ERROR (Texto exacto o código)
        4. PASOS REALIZADOS (Descripción de qué hacía el usuario)
        5. EVIDENCIA (Mención de captura de pantalla o adjunto)

        REGLAS DE DECISIÓN:
        - Si el usuario dice "Hola", "Gracias", "Ok" -> intencion="SALUDO".
        - Si el usuario solo envía un archivo sin texto nuevo -> intencion="APORTE".
        - Si el usuario describe un problema -> intencion="REPORTE".

        SI ES "REPORTE", DEBES LISTAR TEXTUALMENTE QUÉ FALTA.
        Ejemplo: "Falta: Módulo afectado, Mensaje de error y Evidencia."
        
        Si el reporte es MUY corto (ej: "no anda"), ASUME que falta TODO.

        RESPONDE SOLO ESTE JSON:
        {{
            "es_ticket_valido": true,
            "intencion": "REPORTE, SALUDO o APORTE",
            "categoria": "Software/Hardware/Red/Facturación",
            "prioridad": "Baja/Media/Alta",
            "modulo_detectado": "Nombre o 'No especificado'",
            "resumen": "Resumen corto",
            "datos_faltantes": "Lista explicita de lo que falta o 'Ninguno'"
        }}
        """

        response = model.generate_content(prompt)
        match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if match:
            datos_dict = json.loads(match.group(0))
            datos_dict["id_ticket"] = nuevo_id
            return AnalisisTicket(**datos_dict)
        else:
            raise Exception("Error JSON")

    except Exception as e:
        print(f"⚠️ Error IA: {e}")
        return AnalisisTicket(
            es_ticket_valido=True, categoria="General", prioridad="Media", resumen="Manual",
            id_ticket=nuevo_id, modulo_detectado="N/A", datos_faltantes="Revisión humana", intencion="REPORTE"
        )

# --- FUNCIÓN 2: EL GESTOR DE RESPUESTA ---
def generar_respuesta_cliente(cliente_nombre: str, categoria: str, datos_faltantes: str, id_ticket: str, intencion: str, modulo: str):
    try:
        model = genai.GenerativeModel('gemini-pro', generation_config=generation_config)

        # Lógica forzada para asegurar que pida los datos
        if intencion == "SALUDO":
            instruccion = "Agradece y cierra el ticket cortésmente."
        elif intencion == "APORTE":
            instruccion = "Confirma recepción de la evidencia."
        else:
            # REPORTE
            if "Ninguno" in datos_faltantes or "ninguno" in datos_faltantes:
                instruccion = f"Informa que el ticket del módulo {modulo} está completo y fue escalado a Desarrollo."
            else:
                instruccion = f"""
                URGENTE: El usuario NO envió la información necesaria.
                Debes responder solicitando OBLIGATORIAMENTE estos datos faltantes: {datos_faltantes}.
                Usa una lista con viñetas (bullets).
                Sé muy profesional y firme: Sin estos datos no podemos iniciar la gestión.
                """

        prompt = f"""
        Actúa como Gerente de Soporte Nivel 2.
        Cliente: {cliente_nombre}. Ticket: {id_ticket}.
        
        INSTRUCCIÓN: {instruccion}
        
        Estructura del correo:
        1. Saludo formal.
        2. Estado del Ticket.
        3. CUERPO (La solicitud de datos o confirmación).
        4. Cierre profesional.
        """
        
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception:
        return f"Ticket #{id_ticket} actualizado."