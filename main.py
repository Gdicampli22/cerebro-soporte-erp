import os
import google.generativeai as genai
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from agent_tools import crear_ticket_en_db
import json

app = FastAPI()

# Configuración de Gemini
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

# Usamos el modelo Flash por rapidez
model = genai.GenerativeModel('gemini-pro')

class ChatRequest(BaseModel):
    mensaje: str
    cliente: str = "Cliente Desconocido"

@app.get("/")
def home():
    return {"estado": "Cerebro IA activo 🧠"}

@app.post("/chat")
def chat_soporte(request: ChatRequest):
    
    # 1. EL PROMPT DEL SISTEMA
    system_prompt = f"""
    Eres un Agente de Soporte Técnico experto en ERP. Tu cliente es: {request.cliente}.
    
    Tus reglas:
    1. Si el usuario saluda o pregunta algo general, responde amablemente y breve.
    2. Si el usuario reporta un ERROR, FALLA o PROBLEMA:
       - Genera un JSON estricto con la acción "crear_ticket".
       - Prioridad: Alta (sistema caído), Media (error parcial), Baja (dudas).
    
    FORMATO JSON OBLIGATORIO PARA TICKETS:
    {{
      "accion": "crear_ticket",
      "asunto": "Resumen breve del error",
      "prioridad": "Alta/Media/Baja",
      "respuesta_usuario": "Texto para decirle al usuario que ya reportaste el error"
    }}

    Si NO es un ticket, responde solo con texto plano.
    """

    # 2. Consultar a Gemini
    try:
        chat = model.start_chat(history=[])
        response = chat.send_message(f"{system_prompt}\n\nMensaje del usuario: {request.mensaje}")
        texto_respuesta = response.text.strip()

        # 3. Detectar si la IA quiere crear un ticket
        if "crear_ticket" in texto_respuesta:
            # Buscamos el JSON dentro de la respuesta (por si la IA pone texto extra)
            inicio = texto_respuesta.find('{')
            fin = texto_respuesta.rfind('}') + 1
            
            if inicio != -1 and fin != -1:
                json_str = texto_respuesta[inicio:fin]
                datos_ia = json.loads(json_str)

                if datos_ia.get("accion") == "crear_ticket":
                    # ¡EJECUTAMOS LA HERRAMIENTA!
                    resultado = crear_ticket_en_db(
                        cliente=request.cliente,
                        asunto=datos_ia["asunto"],
                        prioridad=datos_ia["prioridad"]
                    )
                    
                    if resultado["status"] == "success":
                        return {
                            "respuesta": f"{datos_ia['respuesta_usuario']} (Ticket ID: {resultado['id']})",
                            "ticket_creado": True
                        }
        
        # Si no es ticket o falla el JSON, devolvemos respuesta normal
        return {"respuesta": texto_respuesta}

    except Exception as e:
        return {"respuesta": f"Error procesando solicitud: {str(e)}"}