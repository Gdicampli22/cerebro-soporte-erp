from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
import re
from supabase import create_client, Client
from agent_tools import analizar_ticket, generar_respuesta_cliente

app = FastAPI()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class EmailSchema(BaseModel):
    mensaje: str
    cliente: str
    asunto: str
    archivos_adjuntos: Optional[str] = None

def buscar_id_existente(asunto: str, cuerpo: str):
    patron = r"(TK-\d{6}-\d{3})"
    match = re.search(patron, asunto)
    if match: return match.group(0)
    match = re.search(patron, cuerpo)
    if match: return match.group(0)
    return None

@app.post("/procesar_email")
def procesar_email(email: EmailSchema):
    try:
        # 1. Análisis Auditoría
        analisis = analizar_ticket(email.mensaje)
        analisis_data = analisis.dict()

        # 2. Generar Respuesta (Le pasamos el modulo detectado)
        respuesta_proactiva = generar_respuesta_cliente(
            email.cliente, 
            analisis_data["categoria"], 
            analisis_data["datos_faltantes"],
            analisis_data["id_ticket"],
            analisis_data["intencion"],
            analisis_data["modulo_detectado"] # <--- Nuevo dato para el correo
        )

        ticket_id_existente = buscar_id_existente(email.asunto, email.mensaje)
        id_final = ticket_id_existente if ticket_id_existente else analisis_data["id_ticket"]

        # --- ACTUALIZACIÓN DE TICKET EXISTENTE ---
        if ticket_id_existente:
            print(f"🔄 Actualizando: {ticket_id_existente}")
            
            data_db = supabase.table("tickets").select("historial, adjuntos").eq("id_ticket", ticket_id_existente).execute()
            
            if data_db.data:
                current = data_db.data[0]
                historial_previo = current.get("historial", "")
                
                nuevo_bloque = f"\n\n========================================\n"
                nuevo_bloque += f"📅 ACTUALIZACIÓN CLIENTE ({email.cliente}):\n{email.mensaje}\n"
                if email.archivos_adjuntos:
                    nuevo_bloque += f"[📎 ADJUNTO NUEVO: {email.archivos_adjuntos}]\n"
                nuevo_bloque += f"----------------------------------------\n"
                nuevo_bloque += f"🤖 GESTIÓN IA:\n{respuesta_proactiva}"
                
                update_data = {
                    "historial": historial_previo + nuevo_bloque,
                    "estado": "En Gestión" if analisis_data["intencion"] == "APORTE" else "Esperando Cliente",
                    "respuesta_ia": respuesta_proactiva
                }
                if email.archivos_adjuntos:
                    prev = current.get("adjuntos", "")
                    update_data["adjuntos"] = f"{prev}, {email.archivos_adjuntos}" if prev else email.archivos_adjuntos

                supabase.table("tickets").update(update_data).eq("id_ticket", ticket_id_existente).execute()

                return {
                    "status": "Ticket Actualizado",
                    "asunto_para_responder": email.asunto,
                    "cuerpo_email_respuesta": respuesta_proactiva
                }

        # --- CREACIÓN DE TICKET NUEVO ---
        print(f"✨ Nuevo Caso: {id_final}")
        nuevo_asunto = f"[{id_final}] {email.asunto}"

        historial_inicial = f"========================================\n"
        historial_inicial += f"🎫 INICIO DE GESTIÓN: {id_final}\n"
        historial_inicial += f"👤 REPORTE ORIGINAL:\n{email.mensaje}\n"
        historial_inicial += f"----------------------------------------\n"
        historial_inicial += f"📋 AUDITORÍA IA:\n"
        historial_inicial += f"- Módulo: {analisis_data['modulo_detectado']}\n"
        historial_inicial += f"- Faltantes: {analisis_data['datos_faltantes']}\n"
        historial_inicial += f"----------------------------------------\n"
        historial_inicial += f"✉️ RESPUESTA INICIAL:\n{respuesta_proactiva}"

        datos_ticket = {
            "id_ticket": id_final,
            "cliente": email.cliente,
            "asunto": email.asunto,
            "descripcion": email.mensaje,
            "resumen": analisis_data["resumen"],
            "categoria": analisis_data["categoria"],
            "prioridad": analisis_data["prioridad"],
            "es_ticket_valido": analisis_data["es_ticket_valido"],
            "estado": "Pendiente Info" if analisis_data["datos_faltantes"] != "Ninguno" else "Escalado",
            "intencion": analisis_data["intencion"],
            "respuesta_ia": respuesta_proactiva,
            "historial": historial_inicial,
            "adjuntos": email.archivos_adjuntos if email.archivos_adjuntos else "Sin adjuntos",
            # Si quieres guardar el módulo, crea la columna 'modulo_erp' en Supabase y descomenta:
            # "modulo_erp": analisis_data["modulo_detectado"] 
        }

        supabase.table("tickets").insert(datos_ticket).execute()

        return {
            "status": "Ticket Creado",
            "asunto_para_responder": nuevo_asunto,
            "cuerpo_email_respuesta": respuesta_proactiva
        }

    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))