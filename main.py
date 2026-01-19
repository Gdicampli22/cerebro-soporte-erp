from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import re # Importamos expresiones regulares para buscar el [TCK]
from supabase import create_client, Client
from agent_tools import analizar_ticket, generar_respuesta_cliente

# --- Configuración ---
app = FastAPI()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class EmailInput(BaseModel):
    mensaje: str
    cliente: str
    asunto: str

@app.get("/")
def read_root():
    return {"estado": "Cerebro Soporte Activo v3 (Con Historial)"}

@app.post("/procesar_email")
def procesar_email(email: EmailInput):
    # 1. BUSCAR SI YA EXISTE UN TICKET (Mirando el Asunto)
    # Buscamos el patrón [TCK-XXXXXX]
    match = re.search(r"\[(TCK-\d+)\]", email.asunto)
    
    if match:
        # --- ES UNA RESPUESTA A UN TICKET EXISTENTE ---
        ticket_id = match.group(1)
        print(f"🔄 Actualización detectada para el ticket: {ticket_id}")
        
        # 1.1 Recuperar el historial actual
        data = supabase.table("tickets").select("historial").eq("id_ticket", ticket_id).execute()
        
        if data.data:
            historial_previo = data.data[0].get('historial') or ""
            
            # 1.2 Agregar el nuevo mensaje
            nuevo_historial = f"{historial_previo}\n\n--- Cliente ({email.cliente}) ---\n{email.mensaje}"
            
            # 1.3 Guardar en Supabase y volver a abrir el ticket si estaba cerrado
            supabase.table("tickets").update({
                "historial": nuevo_historial,
                "estado": "Abierto" # Reabrimos el ticket si el cliente responde
            }).eq("id_ticket", ticket_id).execute()
            
            return {
                "estado": "Actualizado", 
                "id_ticket": ticket_id, 
                "accion": "Ticket actualizado con nueva respuesta del cliente"
            }
        else:
            # Si tiene ID pero no existe en base de datos (raro), lo tratamos como nuevo
            pass

    # --- ES UN TICKET NUEVO (Lógica anterior) ---
    print("✨ Nuevo reporte detectado. Consultando a la IA...")
    
    # 1. La IA analiza el problema
    analisis = analizar_ticket(email.mensaje)
    
    if not analisis:
        return {"razon": "Error al analizar con IA", "estado": "Error"}

    if not analisis.es_ticket_valido:
        return {"razon": "No parece un reporte de soporte", "estado": "Ignorado"}

    # 2. Generar respuesta bonita para el cliente
    respuesta_txt = generar_respuesta_cliente(email.cliente, analisis.categoria, analisis.prioridad)

    # 3. Guardar en Supabase
    datos_ticket = {
        "id_ticket": analisis.id_ticket,
        "cliente": email.cliente,
        "asunto": email.asunto,
        "descripcion": analisis.resumen,  # Guardamos el resumen de la IA
        "categoria": analisis.categoria,
        "prioridad": analisis.prioridad,
        "estado": "Abierto",
        "historial": f"--- Mensaje Original ---\n{email.mensaje}" # Iniciamos el historial
    }
    
    supabase.table("tickets").insert(datos_ticket).execute()

    return {
        "estado": "Ticket Creado",
        "id_ticket": analisis.id_ticket,
        "respuesta_generada": respuesta_txt
    }