import requests
import json

# Tu URL real de Vercel
url = "https://cerebro-soporte-erp.vercel.app/chat"

# El mensaje simulado (Cliente reportando falla)
payload = {
    "mensaje": "URGENTE: Soy de SolarTech. El módulo de facturación se colgó y no podemos emitir facturas a los clientes. Necesito ayuda ya.",
    "cliente": "SolarTech"
}

print(f"📡 Enviando mensaje a: {url}...")

try:
    # Enviamos la petición POST
    response = requests.post(url, json=payload)
    
    # Mostramos lo que respondió la IA
    print("\n🤖 Respuesta de la IA:")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))

except Exception as e:
    print(f"❌ Error conectando: {e}")