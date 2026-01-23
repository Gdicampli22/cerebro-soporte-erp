from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import os
from supabase import create_client, Client
from agent_tools import analizar_ticket, generar_respuesta_cliente

app = FastAPI()

# --- Configuración Supabase ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Modelo de datos (Actualizado para Archivos) ---
class EmailSchema(BaseModel):
    mensaje: str
    cliente: str
    asunto: str
    # Nuevo: Lista de URLs de archivos (Imágenes, PDF) que Make subió a Drive/Storage
    archivos_adjuntos: Optional[str] = None 

@app.post("/procesar_email")
def procesar_email(email: EmailSchema):
    try:
        # 1. IA analiza y detecta faltantes
        analisis = analizar_ticket(email.mensaje)
        
        # Convertimos a diccionario
        analisis_data = analisis.dict()

        # 2. Generamos la respuesta INTELIGENTE (Pidiendo capturas si hace falta)
        respuesta_proactiva = generar_respuesta_cliente(
            email.cliente, 
            analisis_data["categoria"], 
            analisis_data["datos_faltantes"],
            analisis_data["id_ticket"]
        )

        # 3. Preparamos datos para Supabase
        datos_ticket = {
            "id_ticket": analisis_data["id_ticket"],
            "cliente": email.cliente,
            "asunto": email.asunto,
            "descripcion": email.mensaje,
            "resumen": analisis_data["resumen"],
            "categoria": analisis_data["categoria"],
            "prioridad": analisis_data["prioridad"],
            "es_ticket_valido": analisis_data["es_ticket_valido"],
            "estado": "Abierto",
            # Guardamos la respuesta que le dimos a la IA para tener registro
            "respuesta_ia": respuesta_proactiva,
            # Guardamos los links de los archivos (si Make los mandó)
            "adjuntos": email.archivos_adjuntos if email.archivos_adjuntos else "Sin adjuntos"
        }

        # 4. Insertar en DB
        supabase.table("tickets").insert(datos_ticket).execute()

        # 5. Devolver a Make para que envíe el email
        return {
            "status": "Ticket Creado Exitosamente",
            "id_ticket": analisis_data["id_ticket"],
            "accion_requerida": analisis_data["datos_faltantes"],
            "cuerpo_email_respuesta": respuesta_proactiva
        }

    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))