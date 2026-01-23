from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
from supabase import create_client, Client
from agent_tools import analizar_ticket, generar_respuesta_cliente

app = FastAPI()

# --- Configuración Supabase ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Modelo de los datos que llegan de Make ---
class EmailSchema(BaseModel):
    mensaje: str
    cliente: str
    asunto: str

@app.get("/")
def read_root():
    return {"status": "System Online"}

@app.post("/procesar_email")
def procesar_email(email: EmailSchema):
    try:
        # 1. Usar la IA para analizar el problema
        analisis = analizar_ticket(email.mensaje)
        
        # 2. Definir valores por defecto si falla la IA (Paracaídas extra)
        if not analisis:
            analisis_data = {
                "categoria": "Sin Clasificar",
                "prioridad": "Media",
                "resumen": "Error de análisis",
                "id_ticket": "MANUAL",
                "es_ticket_valido": True
            }
        else:
            analisis_data = analisis.dict()

        # 3. Preparar el paquete para Supabase (Mapeo Correcto)
        datos_ticket = {
            "cliente": email.cliente,
            "asunto": email.asunto,
            "descripcion": email.mensaje,          # <--- AQUÍ: Mensaje original completo
            "resumen": analisis_data["resumen"],   # <--- AQUÍ: Resumen corto de la IA
            "categoria": analisis_data["categoria"],
            "prioridad": analisis_data["prioridad"],
            "id_ticket": analisis_data["id_ticket"],
            "es_ticket_valido": analisis_data["es_ticket_valido"],
            "estado": "Abierto",                   # Estado inicial por defecto
            "historial": f"Ticket creado automáticamente para {email.cliente}"
        }

        # 4. Guardar en Supabase
        response = supabase.table("tickets").insert(datos_ticket).execute()

        # 5. Generar respuesta para el usuario
        respuesta_ia = generar_respuesta_cliente(
            email.cliente, 
            analisis_data["categoria"], 
            analisis_data["prioridad"]
        )

        return {
            "status": "Ticket Creado",
            "ticket_id": analisis_data["id_ticket"],
            "respuesta_para_cliente": respuesta_ia
        }

    except Exception as e:
        print(f"❌ Error en main.py: {e}")
        # Importante: Devolver error 500 con detalle para ver en logs si falla
        raise HTTPException(status_code=500, detail=str(e))