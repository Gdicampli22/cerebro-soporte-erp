from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
import re
from supabase import create_client, Client
from agent_tools import analizar_ticket, generar_respuesta_cliente

app = FastAPI()

# --- Configuración Supabase ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Modelo de datos ---
class EmailSchema(BaseModel):
    mensaje: str
    cliente: str
    asunto: str
    archivos_adjuntos: Optional[str] = None  # URLs de archivos (si Make los envía)

# --- Función para buscar ID de Ticket en el Asunto ---
def buscar_id_existente(asunto: str, cuerpo: str):
    # Busca patrones como TCK-XXXX o TK-YYMMDD-XXX
    # Combina asunto y cuerpo por si el cliente borró el ID del asunto pero está en el historial
    texto_completo = f"{asunto} {cuerpo}"
    match = re.search(r"(TK-\d{6}-\d{3}|TCK-\d+)", texto_completo)
    if match:
        return match.group(0)
    return None

@app.post("/procesar_email")
def procesar_email(email: EmailSchema):
    try:
        # 1. ¿Es una respuesta a un ticket existente?
        ticket_id_existente = buscar_id_existente(email.asunto, email.mensaje)

        if ticket_id_existente:
            # --- LÓGICA DE ACTUALIZACIÓN (REPLY) ---
            print(f"🔄 Respuesta detectada para ticket: {ticket_id_existente}")
            
            # Verificar si existe en DB
            respuesta_db = supabase.table("tickets").select("*").eq("id_ticket", ticket_id_existente).execute()
            
            if respuesta_db.data:
                ticket_actual = respuesta_db.data[0]
                
                # Actualizar Historial
                historial_previo = ticket_actual.get("historial", "")
                nuevo_mensaje = f"\n\n--- CLIENTE ({email.cliente}) ---\n{email.mensaje}"
                if email.archivos_adjuntos:
                    nuevo_mensaje += f"\n[Adjuntos: {email.archivos_adjuntos}]"
                
                historial_actualizado = historial_previo + nuevo_mensaje
                
                # Guardar actualización
                supabase.table("tickets").update({
                    "historial": historial_actualizado,
                    "estado": "Respuesta Cliente", # Reabrimos el caso si estaba cerrado
                    "adjuntos": f"{ticket_actual.get('adjuntos', '')} , {email.archivos_adjuntos}" if email.archivos_adjuntos else ticket_actual.get('adjuntos')
                }).eq("id_ticket", ticket_id_existente).execute()

                return {
                    "status": "Ticket Actualizado",
                    "id_ticket": ticket_id_existente,
                    "accion": "Historial actualizado",
                    "cuerpo_email_respuesta": "Gracias por su respuesta. La hemos agregado a su caso."
                }

        # --- LÓGICA DE CREACIÓN (NUEVO TICKET) ---
        print("✨ Creando Nuevo Ticket...")
        
        # 1. IA analiza
        analisis = analizar_ticket(email.mensaje)
        analisis_data = analisis.dict()

        # 2. Generamos la respuesta PROACTIVA
        respuesta_proactiva = generar_respuesta_cliente(
            email.cliente, 
            analisis_data["categoria"], 
            analisis_data["datos_faltantes"],
            analisis_data["id_ticket"]
        )

        # 3. Armamos el Historial Inicial
        # Guardamos lo que dijo el cliente Y lo que le respondió la IA
        historial_inicial = f"--- CLIENTE ({email.cliente}) ---\n{email.mensaje}\n\n--- SOPORTE (IA) ---\n{respuesta_proactiva}"

        # 4. Preparamos datos para Supabase
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
            "respuesta_ia": respuesta_proactiva,
            "historial": historial_inicial,  # <--- AQUÍ SE GUARDA LA IDA Y VUELTA
            "adjuntos": email.archivos_adjuntos if email.archivos_adjuntos else "Sin adjuntos"
        }

        # 5. Insertar en DB
        supabase.table("tickets").insert(datos_ticket).execute()

        return {
            "status": "Ticket Creado",
            "id_ticket": analisis_data["id_ticket"],
            "cuerpo_email_respuesta": respuesta_proactiva
        }

    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))