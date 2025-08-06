from fastapi import FastAPI, Form
from fastapi.responses import PlainTextResponse
import json
import os
import httpx
from datetime import date
from dotenv import load_dotenv
from slack_sdk import WebClient

# Cargar .env
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
if SLACK_BOT_TOKEN:
    print(f"[DEBUG] Token cargado en FastAPI: {SLACK_BOT_TOKEN[:6]}...{SLACK_BOT_TOKEN[-4:]}")
else:
    print("[DEBUG] SLACK_BOT_TOKEN no encontrado en variables de entorno")

client = WebClient(token=SLACK_BOT_TOKEN)
app = FastAPI()

REGISTRO_FILE = "registro_envios.json"


def obtener_nombre_usuario(user_info: dict) -> str:
    """Obtiene solo el real_name del usuario. Si no está en el payload, lo pide a Slack API."""
    real_name = user_info.get("real_name")
    if real_name:
        return real_name

    user_id = user_info.get("id")
    if user_id:
        try:
            slack_resp = client.users_info(user=user_id)
            if slack_resp.get("ok"):
                profile = slack_resp["user"]["profile"]
                return profile.get("real_name") or user_id
        except Exception as e:
            print(f"Error al obtener real_name desde Slack API: {e}")

    return "desconocido"


def registrar_interaccion(tipo: str, data_item: dict):
    """Registra en el archivo JSON la interacción (aceptado o rechazado)."""
    hoy = str(date.today())
    registro = {}

    if os.path.exists(REGISTRO_FILE):
        try:
            with open(REGISTRO_FILE, "r", encoding="utf-8") as f:
                registro = json.load(f)
        except json.JSONDecodeError:
            registro = {}

    if hoy not in registro:
        registro[hoy] = {"aceptados": [], "rechazados": []}

    if tipo == "aceptado":
        registro[hoy]["aceptados"].append(data_item)
    elif tipo == "rechazado":
        registro[hoy]["rechazados"].append(data_item)

    with open(REGISTRO_FILE, "w", encoding="utf-8") as f:
        json.dump(registro, f, indent=2, ensure_ascii=False)


@app.post("/slack/interactivity")
async def slack_interactivity(payload: str = Form(...)):
    data = json.loads(payload)

    user_info = data.get("user", {})
    user_display = obtener_nombre_usuario(user_info)

    actions = data.get("actions", [])
    action = actions[0] if actions else {}
    action_id = action.get("action_id")

    value = action.get("value")
    value_dict = json.loads(value) if value else {}

    sku = value_dict.get("sku")
    marca = value_dict.get("marca")
    modelo = value_dict.get("modelo")
    sucursal = value_dict.get("sucursal", "No especificada")
    channel_id = value_dict.get("channel_id")
    message_ts = value_dict.get("message_ts")

    if action_id == "aceptar_oferta":
        try:
            original_blocks = data.get("message", {}).get("blocks", [])
            updated_blocks = []
            for block in original_blocks:
                if block.get("type") == "actions":
                    updated_blocks.append({
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f":white_check_mark: *Oferta aceptada por* `{user_display}`"
                            }
                        ]
                    })
                else:
                    updated_blocks.append(block)

            client.chat_update(
                channel=channel_id,
                ts=message_ts,
                text=f"Oferta aceptada por {user_display}",
                blocks=updated_blocks
            )

            # Registrar en archivo
            registrar_interaccion("aceptado", {
                "sku": sku,
                "marca": marca,
                "modelo": modelo,
                "sucursal": sucursal,
                "usuario": user_display
            })

        except Exception as e:
            print(f"Error al actualizar mensaje: {e}")

        respuesta = f":white_check_mark: ¡Oferta aceptada para SKU {sku} por {user_display}!"

    elif action_id == "rechazar_oferta":
        try:
            original_blocks = data.get("message", {}).get("blocks", [])
            updated_blocks = []

            img_url = None
            descripcion = None

            for block in original_blocks:
                if block.get("type") == "image" and block.get("image_url"):
                    img_url = block.get("image_url")
                elif block.get("type") == "section" and "text" in block:
                    texto = block["text"]["text"]
                    lineas = texto.split("\n")
                    desc_line = next((l.replace("*Descripción:*", "").strip() for l in lineas if "*Descripción:*" in l), "")
                    if desc_line:
                        descripcion = desc_line

            updated_blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Prenda/SKU:* {sku}\n*Descripción:* {descripcion or ''}"
                },
                "accessory": {
                    "type": "image",
                    "image_url": img_url or "https://via.placeholder.com/48",
                    "alt_text": f"Imagen de {marca} {modelo}"
                }
            })

            updated_blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f":x: *Oferta rechazada por* `{user_display}`"
                    }
                ]
            })

            client.chat_update(
                channel=channel_id,
                ts=message_ts,
                text=f"Oferta rechazada por {user_display}",
                blocks=updated_blocks
            )

            # Registrar en archivo
            registrar_interaccion("rechazado", {
                "sku": sku,
                "marca": marca,
                "modelo": modelo,
                "sucursal": sucursal,
                "usuario": user_display
            })

        except Exception as e:
            print(f"Error al actualizar mensaje en rechazo: {e}")

        respuesta = f":x: Oferta rechazada para SKU {sku} por {user_display}."

    else:
        respuesta = "Acción no reconocida."

    return PlainTextResponse(respuesta)


@app.get("/")
async def home():
    return {"ok": True, "message": "Slack webhook activo"}
