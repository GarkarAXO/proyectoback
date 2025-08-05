from fastapi import FastAPI, Form
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv
import json
import os
import httpx

dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")

# Debug: mostrar parte del token cargado
if SLACK_BOT_TOKEN:
    print(f"[DEBUG] Token cargado en FastAPI: {SLACK_BOT_TOKEN[:6]}...{SLACK_BOT_TOKEN[-4:]}")
else:
    print("[DEBUG] SLACK_BOT_TOKEN no encontrado en variables de entorno")

# 3️⃣ Crear la app FastAPI
app = FastAPI()

async def borrar_mensaje(channel_id, message_ts):
    url = "https://slack.com/api/chat.delete"
    headers = {
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "channel": channel_id,
        "ts": message_ts
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, data=data, headers=headers)
        result = response.json()
        print("Slack chat.delete response:", result)
        if not result.get("ok"):
            print(f"Error al borrar mensaje: {result.get('error')}")

@app.post("/slack/interactivity")
async def slack_interactivity(payload: str = Form(...)):
    """
    Endpoint para recibir interacciones de Slack (botones).
    Ahora usa channel_id y message_ts desde el value del botón.
    """
    print(f"PAYLOAD recibido: {repr(payload)}")
    data = json.loads(payload)

    # Datos del usuario y acción
    user = data.get("user", {}).get("username", "desconocido")
    actions = data.get("actions", [])
    action = actions[0] if actions else {}
    action_id = action.get("action_id")
    
    # Decodificar value del botón
    value = action.get("value")
    value_dict = json.loads(value) if value else {}

    sku = value_dict.get("sku")
    marca = value_dict.get("marca")
    modelo = value_dict.get("modelo")
    channel_id = value_dict.get("channel_id")
    message_ts = value_dict.get("message_ts")

    print(f"Usuario: {user} - Acción: {action_id} - SKU: {sku}, Marca: {marca}, Modelo: {modelo}")
    print(f"Canal: {channel_id}, Message TS: {message_ts}")

    # Procesar acción
    if action_id == "aceptar_oferta":
        respuesta = f":white_check_mark: ¡Oferta aceptada para SKU {sku}!"
    elif action_id == "rechazar_oferta":
        respuesta = f":x: Oferta rechazada para SKU {sku}."
        if channel_id and message_ts:
            await borrar_mensaje(channel_id, message_ts)
        else:
            print("⚠ No se pudo borrar el mensaje: faltan channel_id o message_ts en el value.")
    else:
        respuesta = "Acción no reconocida."

    return PlainTextResponse(respuesta)

@app.get("/")
async def home():
    return {"ok": True, "message": "Slack webhook activo"}
