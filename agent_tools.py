import os
import datetime
from supabase import create_client

# Conexión a Supabase (busca las variables de entorno)
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase = create_client(url, key) if url and key else None

def crear_ticket_en_db(cliente, asunto, prioridad, agente="IA"):
    """
    Función técnica que inserta el ticket en Supabase.
    """
    if not supabase:
        return {"status": "error", "mensaje": "No hay conexión con la base de datos Supabase"}

    # Generamos un ID corto basado en la hora (ej: TCK-182030)
    ticket_id = f"TCK-{datetime.datetime.now().strftime('%d%H%M')}"
    
    datos = {
        "id_ticket": ticket_id,
        "empresa": cliente,
        "titulo": asunto,
        "prioridad": prioridad,
        "agente_soporte": agente,
        "estado": "Abierto",
        "fecha_creacion": datetime.datetime.now().isoformat(),
        "modulo_erp": "General"
    }

    try:
        # Insertamos en la tabla 'tickets'
        supabase.table("tickets").insert(datos).execute()
        return {"status": "success", "id": ticket_id, "mensaje": "Ticket guardado correctamente"}
    except Exception as e:
        return {"status": "error", "mensaje": str(e)}