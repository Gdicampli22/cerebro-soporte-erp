from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
import re
from supabase import create_client, Client
from agent_tools import analizar_ticket, generar_respuesta_cliente

app = FastAPI()

# --- Conexión DB ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Modelo ---
class EmailSchema(BaseModel):
    mensaje: str
    cliente: str
    asunto: str
    archivos_adjuntos: Optional[str] = None

# --- Buscar ID (Regex mejorado) ---
def buscar_id_existente(asunto: str, cuerpo: str):
    patron = r"(TK-\d{6}-\d{3})" # Busca formato TK-AAMMDD-XXX
    match = re.search(patron, asunto)
    if match: return match.group(0)
    match = re.search(patron, cuerpo)
    if match: return match.group(0)
    return None

@app.post("/procesar_email")
def procesar_email(email: EmailSchema):
    try:
        # 1. Analizar el contenido primero (para saber la intención)
        analisis = analizar_ticket(email.mensaje)
        analisis_data = analisis.dict()

        # 2. Verificar si es Hilo (Respuesta) o Nuevo
        ticket_id_existente = buscar_id_existente(email.asunto, email.mensaje)
        
        # ID a usar: El existente si lo hay, o el nuevo generado por la IA
        id_final = ticket_id_existente if ticket_id_existente else analisis_data["id_ticket"]

        # 3. Generar la Respuesta Profesional usando la INTENCIÓN detectada
        respuesta_proactiva = generar_respuesta_cliente(
            email.cliente, 
            analisis_data["categoria"], 
            analisis_data["datos_faltantes"],
            id_final,
            analisis_data["intencion"] # <--- Clave para que no responda tonterías
        )

        # CASO A: Es una respuesta a un Ticket existente
        if ticket_id_existente:
            print(f"🔄 Actualizando Ticket: {ticket_id_existente} | Intención: {analisis_data['intencion']}")
            
            # Traer historial actual
            data_db = supabase.table("tickets").select("historial, adjuntos").eq("id_ticket", ticket_id_existente).execute()
            
            if data_db.data:
                current = data_db.data[0]
                historial_previo = current.get("historial", "")
                
                # Construir el bloque nuevo del historial
                nuevo_bloque = f"\n\n========================================\n"
                nuevo_bloque += f"📅 FECHA: {re.sub(r'TK-(\d{6})-.*', r'20\1', ticket_id_existente)} (Actualización)\n"
                nuevo_bloque += f"👤 CLIENTE ({email.cliente}):\n{email.mensaje}\n"
                if email.archivos_adjuntos:
                    nuevo_bloque += f"[📎 ADJUNTO: {email.archivos_adjuntos}]\n"
                nuevo_bloque += f"----------------------------------------\n"
                nuevo_bloque += f"🤖 RESPUESTA AUTOMÁTICA:\n{respuesta_proactiva}"
                
                # Actualizar DB
                update_data = {
                    "historial": historial_previo + nuevo_bloque,
                    "estado": "Respuesta Cliente",
                    "respuesta_ia": respuesta_proactiva
                }
                if email.archivos_adjuntos:
                    prev_adjuntos = current.get("adjuntos", "")
                    update_data["adjuntos"] = f"{prev_adjuntos}, {email.archivos_adjuntos}" if prev_adjuntos else email.archivos_adjuntos

                supabase.table("tickets").update(update_data).eq("id_ticket", ticket_id_existente).execute()

                return {
                    "status": "Ticket Actualizado",
                    "tipo": "UPDATE",
                    "asunto_para_responder": email.asunto, # Mantiene el RE:
                    "cuerpo_email_respuesta": respuesta_proactiva
                }

        # CASO B: Es un Ticket Nuevo
        print(f"✨ Nuevo Ticket: {id_final}")
        
        # Asunto formateado para seguimiento futuro
        nuevo_asunto = f"[{id_final}] {email.asunto}"

        # Historial inicial limpio y ordenado
        historial_inicial = f"========================================\n"
        historial_inicial += f"🎫 TICKET CREADO: {id_final}\n"
        historial_inicial += f"👤 CLIENTE: {email.cliente}\n"
        historial_inicial += f"📝 MENSAJE ORIGINAL:\n{email.mensaje}\n"
        historial_inicial += f"----------------------------------------\n"
        historial_inicial += f"🤖 ANÁLISIS IA:\n- Categoría: {analisis_data['categoria']}\n- Prioridad: {analisis_data['prioridad']}\n- Acción: {analisis_data['intencion']}\n"
        historial_inicial += f"----------------------------------------\n"
        historial_inicial += f"✉️ RESPUESTA ENVIADA:\n{respuesta_proactiva}"

        datos_ticket = {
            "id_ticket": id_final,
            "cliente": email.cliente,
            "asunto": email.asunto,
            "descripcion": email.mensaje,
            "resumen": analisis_data["resumen"],
            "categoria": analisis_data["categoria"],
            "prioridad": analisis_data["prioridad"],
            "es_ticket_valido": analisis_data["es_ticket_valido"],
            "estado": "Abierto",
            "intencion": analisis_data["intencion"], # Guardamos la intención también
            "respuesta_ia": respuesta_proactiva,
            "historial": historial_inicial,
            "adjuntos": email.archivos_adjuntos if email.archivos_adjuntos else "Sin adjuntos"
        }

        # Si no existe la columna 'intencion' en supabase, no pasa nada, se ignora o da error leve, 
        # pero idealmente agrégala si quieres trackear KPIs. Si no, borra esa línea del dict.
        
        supabase.table("tickets").insert(datos_ticket).execute()

        return {
            "status": "Ticket Creado",
            "tipo": "NEW",
            "asunto_para_responder": nuevo_asunto,
            "cuerpo_email_respuesta": respuesta_proactiva
        }

    except Exception as e:
        print(f"❌ Error Critical: {e}")
        raise HTTPException(status_code=500, detail=str(e))