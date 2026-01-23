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

# Temperatura un poco más alta para permitir "creatividad" al diagnosticar
generation_config = {
  "temperature": 0.3, 
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
    razonamiento_ia: str # Nuevo: Para ver qué pensó la IA

# --- Función Auxiliar ---
def generar_id_ticket():
    fecha = datetime.datetime.now().strftime("%y%m%d")
    suffix = str(random.randint(100, 999))
    return f"TK-{fecha}-{suffix}"

# --- FUNCIÓN 1: EL DIAGNOSTICADOR (Cerebro) ---
def analizar_ticket(mensaje_usuario: str):
    nuevo_id = generar_id_ticket()

    if not GOOGLE_API_KEY:
        return AnalisisTicket(es_ticket_valido=True, categoria="Error", prioridad="Alta", resumen="Falta API Key", id_ticket=nuevo_id, modulo_detectado="N/A", datos_faltantes="N/A", intencion="REPORTE", razonamiento_ia="Sin API")

    # --- LISTA DE MODELOS A PROBAR (Respaldo Automático) ---
    modelos = ['gemini-3-flash-preview']
    
    for nombre_modelo in modelos:
        try:
            model = genai.GenerativeModel(nombre_modelo, generation_config=generation_config)

            prompt = f"""
            ACTÚA COMO: Ingeniero de Soporte Nivel 3 (Experto en Diagnóstico).
            TAREA: Analizar el reporte del usuario y determinar QUÉ INFORMACIÓN FALTA para resolver el caso.

            MENSAJE DEL USUARIO: "{mensaje_usuario}"

            PASO 1: DETECTAR INTENCIÓN
            - Si es solo "Gracias", "Ok" -> intencion="SALUDO".
            - Si envía solo un archivo -> intencion="APORTE".
            - Si reporta un problema -> intencion="REPORTE".

            PASO 2: RAZONAMIENTO DE DIAGNÓSTICO (Solo para REPORTE)
            No uses una checklist genérica. PIENSA qué se necesita según el caso.
            
            EJEMPLOS DE RAZONAMIENTO:
            - Caso: "No imprime la factura".
              -> Necesito: Nombre de la impresora, si da error en pantalla, y si pasa con todas las facturas.
            - Caso: "El sistema está lento".
              -> Necesito: ¿Es en todos los módulos?, ¿Pasa en una sola PC o en todas?, Proveedor de internet.
            - Caso: "Error 505 en Login".
              -> Necesito: Captura de pantalla del error y usuario afectado.

            PASO 3: GENERAR SALIDA
            Si faltan datos, en 'datos_faltantes' escribe una LISTA CLARA y AMABLE de lo que necesitamos pedirle al cliente.
            Si el reporte es completo, pon 'Ninguno'.

            RESPONDE SOLO JSON:
            {{
                "es_ticket_valido": true,
                "intencion": "REPORTE, SALUDO o APORTE",
                "categoria": "Software/Hardware/Red/Facturación",
                "prioridad": "Baja/Media/Alta",
                "modulo_detectado": "Nombre del módulo (ej: Ventas) o 'General'",
                "resumen": "Resumen del problema",
                "razonamiento_ia": "Explica brevemente por qué pides esos datos",
                "datos_faltantes": "La lista de preguntas para el cliente o 'Ninguno'"
            }}
            """

            response = model.generate_content(prompt)
            match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if match:
                datos_dict = json.loads(match.group(0))
                datos_dict["id_ticket"] = nuevo_id
                # Si el modelo no devolvió razonamiento (versiones viejas), lo rellenamos
                if "razonamiento_ia" not in datos_dict: datos_dict["razonamiento_ia"] = "Análisis automático"
                
                return AnalisisTicket(**datos_dict)
        
        except Exception as e:
            print(f"⚠️ Falló modelo {nombre_modelo}: {e}. Intentando siguiente...")
            continue # Si falla, prueba el siguiente modelo de la lista

    # Si fallan todos
    return AnalisisTicket(
        es_ticket_valido=True, categoria="General", prioridad="Media", resumen="Error IA",
        id_ticket=nuevo_id, modulo_detectado="N/A", datos_faltantes="Revisión humana requerida", intencion="REPORTE", razonamiento_ia="Fallo total IA"
    )

# --- FUNCIÓN 2: EL AGENTE EMPÁTICO (Voz) ---
def generar_respuesta_cliente(cliente_nombre: str, categoria: str, datos_faltantes: str, id_ticket: str, intencion: str, modulo: str):
    # Intentamos primero con el modelo inteligente, si falla vamos al pro
    modelos = ['gemini-1.5-flash', 'gemini-pro']

    for nombre_modelo in modelos:
        try:
            model = genai.GenerativeModel(nombre_modelo, generation_config=generation_config)

            # --- ESTRATEGIA DE RESPUESTA ---
            if intencion == "SALUDO":
                objetivo = "Agradecer el contacto, confirmar que el ticket sigue abierto/cerrado según corresponda y saludar profesionalmente."
            elif intencion == "APORTE":
                objetivo = "Confirmar la recepción de la nueva información. Indicar que el equipo técnico la analizará para avanzar con la solución."
            else:
                # REPORTE
                if "Ninguno" in datos_faltantes or "ninguno" in datos_faltantes:
                    objetivo = f"Informar que el reporte es excelente y completo. Confirmar que el caso sobre '{modulo}' ha sido derivado a los especialistas. Dar tranquilidad."
                else:
                    objetivo = f"""
                    TU OBJETIVO ES OBTENER INFORMACIÓN SIN SONAR COMO UN ROBOT.
                    Explica al cliente que para resolver su problema de '{categoria}', necesitamos entender mejor la situación.
                    
                    SOLICITA EXACTAMENTE ESTO:
                    {datos_faltantes}
                    
                    Usa un tono colaborativo: "Para poder ayudarle mejor...", "Necesitaríamos que nos indique..."
                    """

            prompt = f"""
            ACTÚA COMO: Agente Senior de Customer Success (Empresa de Software ERP).
            TONO: Profesional, Cercano, Resolutivo, Educado (Estilo Corporativo Premium).
            IDIOMA: Español Neutro.

            CONTEXTO:
            - Cliente: {cliente_nombre}
            - Ticket: #{id_ticket}
            - Situación: {objetivo}

            TAREA:
            Redacta la respuesta de correo electrónico.
            
            REGLAS DE FORMATO:
            1. Saludo personalizado.
            2. Referencia al Ticket.
            3. CUERPO: Desarrolla el objetivo con claridad. Si pides datos, usa viñetas (-).
            4. Recordatorio de adjuntos si aplica.
            5. Firma: "El Equipo de Soporte".

            IMPORTANTE: No uses frases robóticas como "En respuesta a su solicitud". Sé natural.
            """
            
            response = model.generate_content(prompt)
            return response.text.strip()
        
        except Exception:
            continue

    return f"Estimado {cliente_nombre}, ticket #{id_ticket} actualizado. Aguardamos su respuesta."