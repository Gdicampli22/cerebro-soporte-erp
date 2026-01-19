import os
import google.generativeai as genai
from fastapi import FastAPI, Request
from pydantic import BaseModel
from agent_tools import crear_ticket_en_db
import json
import re

app = FastAPI()

# Configuración de Gemini
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

# Usamos Flash 1.5
model = genai.GenerativeModel('gemini-3-flash-preview')

# Modelo de datos actualizado para recibir E-MAILS
class EmailRequest(BaseModel):
    mensaje: str       # El cuerpo del correo
    cliente: str       # El correo del remitente (ej: juan@solartech.com)
    asunto: str = "Sin asunto" # El título del correo

def limpiar_json(texto):
    """Limpia el texto para extraer solo el JSON"""
    try:
        match = re.search(r'\{.*\}', texto, re.DOTALL)
        if match:
            return match.group(0)
        return texto
    except:
        return texto

@app.get("/")
def home():
    return {"estado": "Cerebro IA listo para Emails 📧"}

@app.post("/procesar_email") # Cambiamos el nombre del endpoint para ser más claros
def procesar_email(request: EmailRequest):
    
    # PROMPT ESPECIALIZADO EN CORREOS
    system_prompt = f"""
    Actúas como un Agente de Soporte Técnico ERP automático.
    Acabas de recibir un CORREO ELECTRÓNICO.
    
    - Remitente: {request.cliente}
    - Asunto: {request.asunto}
    
    Tus instrucciones:
    1. Analiza si el correo reporta un problema, error o solicitud de soporte.
    2. Si es un problema técnico:
       - Genera un JSON con "accion": "crear_ticket".
       - Define la prioridad basándote en el tono y urgencia del correo.
       - Extrae la empresa basándote en el dominio del correo (ej: @solartech.com -> SolarTech).
    
    3. Si es SPAM, publicidad o algo irrelevante, responde con texto plano ignorándolo.

    FORMATO JSON OBLIGATORIO:
    {{
      "accion": "crear_ticket",
      "empresa_detectada": "Nombre de la empresa (o 'Desconocido')",
      "asunto_ticket": "Título técnico resumen",
      "prioridad": "Alta/Media/Baja",
      "respuesta_para_email": "Redacta una respuesta formal de correo confirmando el ticket"
    }}
    """

    try:
        chat = model.start_chat(history=[])
        # Combinamos asunto y mensaje para que la IA lea todo
        prompt_completo = f"{system_prompt}\n\nCUERPO DEL CORREO:\n{request.mensaje}"
        
        response = chat.send_message(prompt_completo)
        texto_crudo = response.text.strip()
        json_limpio = limpiar_json(texto_crudo)

        # Detectamos si quiere crear ticket
        if "crear_ticket" in json_limpio:
            try:
                datos_ia = json.loads(json_limpio)
                
                if datos_ia.get("accion") == "crear_ticket":
                    # Usamos la empresa que detectó la IA o el email si no encontró nombre
                    cliente_final = datos_ia.get("empresa_detectada", request.cliente)
                    
                    # EJECUTAR HERRAMIENTA DB
                    resultado = crear_ticket_en_db(
                        cliente=cliente_final,
                        asunto=datos_ia.get("asunto_ticket", request.asunto),
                        prioridad=datos_ia.get("prioridad", "Media")
                    )
                    
                    if resultado["status"] == "success":
                        return {
                            "estado": "Ticket Creado",
                            "id_ticket": resultado["id"],
                            "respuesta_generada": datos_ia['respuesta_para_email']
                        }
                    else:
                        return {"estado": "Error DB", "detalle": resultado["mensaje"]}
            
            except json.JSONDecodeError:
                return {"estado": "Error IA", "detalle": "La IA no generó un JSON válido", "raw": texto_crudo}

        # Si no era ticket
        return {"estado": "Ignorado", "razon": "No parece un reporte de soporte", "respuesta_ia": texto_crudo}

    except Exception as e:
        return {"estado": "Error Servidor", "detalle": str(e)}