from fastapi import FastAPI, Request, Form
from fastapi.responses import PlainTextResponse
import json
import os
import httpx
from slack_sdk import WebClient

app = FastAPI()
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")

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
        print("Slack chat.delete response:", response.text)

@app.post("/slack/interactivity")
async def slack_interactivity(payload: str = Form(...)):
    data = json.loads(payload)
    user = data["user"]["username"]
    actions = data["actions"]
    action = actions[0] if actions else {}
    action_id = action.get("action_id")
    value = action.get("value")
    value_dict = json.loads(value) if value else {}

    sku = value_dict.get("sku")
    marca = value_dict.get("marca")
    modelo = value_dict.get("modelo")

    # --- Obtener channel_id y message_ts ---
    channel_id = data.get("channel", {}).get("id")
    message_ts = data.get("message", {}).get("ts")

    print(f"Usuario: {user} - Acción: {action_id} - SKU: {sku}, Marca: {marca}, Modelo: {modelo}")

    # --- Procesa la acción ---
    if action_id == "aceptar_oferta":
        respuesta = f":white_check_mark: ¡Oferta aceptada para SKU {sku}!"
    elif action_id == "rechazar_oferta":
        respuesta = f":x: Oferta rechazada para SKU {sku}."
        # BORRAR el mensaje (opcionalmente puedes poner un await aquí si quieres esperar)
        if channel_id and message_ts:
            await borrar_mensaje(channel_id, message_ts)
    else:
        respuesta = "Acción no reconocida."

    return PlainTextResponse(respuesta)

@app.get("/")
async def home():
    return {"ok": True, "message": "Slack webhook activo"}
