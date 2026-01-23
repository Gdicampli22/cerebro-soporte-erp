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
    archivos_adjuntos: Optional[str] = None

# --- Función CRÍTICA: Buscar ID en el Asunto ---
def buscar_id_existente(asunto: str, cuerpo: str):
    # Buscamos el formato exacto que generamos: TK-AAMMDD-XXX
    # Prioridad: Buscar en el Asunto primero (es más fiable)
    patron = r"(TK-\d{6}-\d{3})"
    
    match_asunto = re.search(patron, asunto)
    if match_asunto:
        return match_asunto.group(0)
    
    match_cuerpo = re.search(patron, cuerpo)
    if match_cuerpo:
        return match_cuerpo.group(0)
        
    return None

@app.post("/procesar_email")
def procesar_email(email: EmailSchema):
    try:
        # 1. Intentamos detectar si ya existe el ticket (Hilo de conversación)
        ticket_id_existente = buscar_id_existente(email.asunto, email.mensaje)

        if ticket_id_existente:
            print(f"🔄 Hilo detectado: {ticket_id_existente}")
            
            # Verificar si existe en DB
            respuesta_db = supabase.table("tickets").select("*").eq("id_ticket", ticket_id_existente).execute()
            
            if respuesta_db.data:
                ticket_actual = respuesta_db.data[0]
                
                # Armamos el nuevo historial
                historial_previo = ticket_actual.get("historial", "")
                nuevo_mensaje = f"\n\n--- CLIENTE ({email.cliente}) ---\n{email.mensaje}"
                
                # Si trae archivos (fotos), los registramos en el historial
                nuevos_adjuntos = ""
                if email.archivos_adjuntos:
                    nuevo_mensaje += f"\n[📎 Archivo Adjunto Recibido: {email.archivos_adjuntos}]"
                    nuevos_adjuntos = f"{ticket_actual.get('adjuntos', '')}, {email.archivos_adjuntos}" if ticket_actual.get('adjuntos') else email.archivos_adjuntos
                
                # Actualizamos Supabase
                datos_update = {
                    "historial": historial_previo + nuevo_mensaje,
                    "estado": "Respuesta Cliente", # Reabre el ticket
                }
                if nuevos_adjuntos:
                    datos_update["adjuntos"] = nuevos_adjuntos

                supabase.table("tickets").update(datos_update).eq("id_ticket", ticket_id_existente).execute()

                # IMPORTANTE: Devolvemos el asunto original para mantener el hilo en Gmail
                return {
                    "status": "Ticket Actualizado",
                    "tipo": "UPDATE",
                    "id_ticket": ticket_id_existente,
                    "asunto_para_responder": email.asunto, # Mantenemos el RE: ...
                    "cuerpo_email_respuesta": "Hemos recibido su respuesta y archivo adjunto. Un agente lo revisará."
                }

        # 2. Si NO existe ID, creamos Ticket Nuevo
        print("✨ Creando Nuevo Ticket...")
        
        analisis = analizar_ticket(email.mensaje)
        analisis_data = analisis.dict()

        respuesta_proactiva = generar_respuesta_cliente(
            email.cliente, 
            analisis_data["categoria"], 
            analisis_data["datos_faltantes"],
            analisis_data["id_ticket"]
        )

        # --- TRUCO MAESTRO: INYECTAR ID EN EL ASUNTO ---
        # Si el asunto era "No anda la impresora", ahora será "[TK-240123-123] No anda la impresora"
        # Esto garantiza que cuando el cliente responda, capturemos el ID.
        nuevo_asunto_con_id = f"[{analisis_data['id_ticket']}] {email.asunto}"

        datos_ticket = {
            "id_ticket": analisis_data["id_ticket"],
            "cliente": email.cliente,
            "asunto": email.asunto, # Guardamos el original limpio en DB
            "descripcion": email.mensaje,
            "resumen": analisis_data["resumen"],
            "categoria": analisis_data["categoria"],
            "prioridad": analisis_data["prioridad"],
            "es_ticket_valido": analisis_data["es_ticket_valido"],
            "estado": "Abierto",
            "respuesta_ia": respuesta_proactiva,
            "historial": f"--- TICKET CREADO ---\n{email.mensaje}\n\n--- RESPUESTA IA ---\n{respuesta_proactiva}",
            "adjuntos": email.archivos_adjuntos if email.archivos_adjuntos else "Sin adjuntos"
        }

        supabase.table("tickets").insert(datos_ticket).execute()

        return {
            "status": "Ticket Creado",
            "tipo": "NEW",
            "id_ticket": analisis_data["id_ticket"],
            "asunto_para_responder": nuevo_asunto_con_id, # <--- ESTE ES EL DATO CLAVE PARA MAKE
            "cuerpo_email_respuesta": respuesta_proactiva
        }

    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))