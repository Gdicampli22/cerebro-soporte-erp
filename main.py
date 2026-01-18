import os
import google.generativeai as genai
from fastapi import FastAPI
from pydantic import BaseModel
from agent_tools import crear_ticket_en_db
import json
import re

app = FastAPI()

# Configuración de Gemini
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

# Usamos Flash 1.5 que es rápido y acepta instrucciones complejas
model = genai.GenerativeModel('gemini-1.5-flash')

class ChatRequest(BaseModel):
    mensaje: str
    cliente: str = "Cliente Desconocido"

def limpiar_json(texto):
    """
    Busca el primer '{' y el último '}' para extraer solo el JSON,
    ignorando texto extra o markdown como ```json
    """
    try:
        # Busca el patrón de un objeto JSON
        match = re.search(r'\{.*\}', texto, re.DOTALL)
        if match:
            return match.group(0)
        return texto
    except:
        return texto

@app.get("/")
def home():
    return {"estado": "Cerebro IA activo y mejorado 🧠 v2"}

@app.post("/chat")
def chat_soporte(request: ChatRequest):
    
    # PROMPT MEJORADO: Le prohibimos hablar, solo JSON
    system_prompt = f"""
    Eres un sistema experto de soporte ERP. 
    Tu trabajo es clasificar el mensaje del cliente: {request.cliente}.

    SI EL USUARIO REPORTA UN PROBLEMA (Error, Falla, Caída, No funciona):
    Debes RESPONDER ÚNICAMENTE con este formato JSON (sin texto extra):
    {{
      "accion": "crear_ticket",
      "asunto": "Resumen técnico corto del error",
      "prioridad": "Alta", 
      "respuesta_usuario": "Mensaje amable confirmando el ticket"
    }}
    Nota: Prioridad 'Alta' si afecta facturación o acceso. 'Media' si es funcional. 'Baja' si es duda.

    SI ES SOLO UN SALUDO O DUDA GENERAL:
    Responde con texto plano normal.
    """

    try:
        chat = model.start_chat(history=[])
        response = chat.send_message(f"{system_prompt}\n\nINPUT USUARIO: {request.mensaje}")
        texto_crudo = response.text.strip()

        # 1. Limpieza agresiva del JSON
        json_limpio = limpiar_json(texto_crudo)

        # 2. Intentamos leerlo como JSON
        if '"accion": "crear_ticket"' in json_limpio or "crear_ticket" in json_limpio:
            try:
                datos_ia = json.loads(json_limpio)
                
                if datos_ia.get("accion") == "crear_ticket":
                    # ¡EJECUTAR HERRAMIENTA!
                    resultado = crear_ticket_en_db(
                        cliente=request.cliente,
                        asunto=datos_ia.get("asunto", "Ticket sin asunto"),
                        prioridad=datos_ia.get("prioridad", "Media")
                    )
                    
                    # Devolvemos éxito con el ID del ticket para verificar
                    if resultado["status"] == "success":
                        return {
                            "respuesta": f"{datos_ia['respuesta_usuario']}",
                            "info_ticket": f"✅ Ticket Creado ID: {resultado['id']}",
                            "ticket_creado": True
                        }
                    else:
                        return {
                            "respuesta": "Hubo un error técnico guardando el ticket.",
                            "debug_error": resultado["mensaje"]
                        }
            except json.JSONDecodeError:
                # Si falló el JSON, devolvemos el texto pero avisamos
                return {
                    "respuesta": "La IA intentó crear un ticket pero el formato falló.",
                    "debug_raw": texto_crudo
                }

        # Si no era ticket, respuesta normal
        return {"respuesta": texto_crudo}

    except Exception as e:
        return {"respuesta": f"Error crítico en el servidor: {str(e)}"}