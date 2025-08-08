from fastapi import FastAPI, Form
from fastapi.responses import PlainTextResponse
import json
import os
import httpx
from datetime import date
from dotenv import load_dotenv
from slack_sdk import WebClient

dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
if SLACK_BOT_TOKEN:
    print(f"[DEBUG] Token loaded in FastAPI: {SLACK_BOT_TOKEN[:6]}...{SLACK_BOT_TOKEN[-4:]}")
else:
    print("[DEBUG] SLACK_BOT_TOKEN not found in environment variables")

client = WebClient(token=SLACK_BOT_TOKEN)
app = FastAPI()

INTERACTION_LOG_FILE = "interaction_log.json"

def get_user_display_name(user_info: dict) -> str:
    """Gets the real_name of the user from payload or Slack API."""
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
            print(f"Error retrieving real_name from Slack API: {e}")

    return "desconocido"

def register_interaction(action_type: str, data_item: dict):
    """Registers interaction (accepted/rejected) in a JSON file by date."""
    today = str(date.today())
    log_data = {}

    if os.path.exists(INTERACTION_LOG_FILE):
        try:
            with open(INTERACTION_LOG_FILE, "r", encoding="utf-8") as f:
                log_data = json.load(f)
        except json.JSONDecodeError:
            log_data = {}

    if today not in log_data:
        log_data[today] = {"accepted": [], "rejected": []}

    if action_type == "accepted":
        log_data[today]["accepted"].append(data_item)
    elif action_type == "rejected":
        log_data[today]["rejected"].append(data_item)

    with open(INTERACTION_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)

@app.post("/slack/interactivity")
async def slack_interactivity(payload: str = Form(...)):
    data = json.loads(payload)

    user_info = data.get("user", {})
    user_display = get_user_display_name(user_info)

    actions = data.get("actions", [])
    action = actions[0] if actions else {}
    action_id = action.get("action_id")

    value = action.get("value")
    value_dict = json.loads(value) if value else {}

    sku = value_dict.get("sku")
    brand = value_dict.get("marca")
    model = value_dict.get("modelo")
    branch = value_dict.get("sucursal", "No especificada")
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

            register_interaction("accepted", {
                "sku": sku,
                "brand": brand,
                "model": model,
                "branch": branch,
                "user": user_display
            })

        except Exception as e:
            print(f"Error updating Slack message: {e}")

        response_text = f":white_check_mark: ¡Oferta aceptada para SKU {sku} por {user_display}!"

    elif action_id == "rechazar_oferta":
        try:
            original_blocks = data.get("message", {}).get("blocks", [])
            updated_blocks = []

            img_url = None
            description = None

            for block in original_blocks:
                if block.get("type") == "image" and block.get("image_url"):
                    img_url = block.get("image_url")
                elif block.get("type") == "section" and "text" in block:
                    text = block["text"]["text"]
                    lines = text.split("\n")
                    desc_line = next((l.replace("*Descripción:*", "").strip() for l in lines if "*Descripción:*" in l), "")
                    if desc_line:
                        description = desc_line

            updated_blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Prenda/SKU:* {sku}\n*Descripción:* {description or ''}"
                },
                "accessory": {
                    "type": "image",
                    "image_url": img_url or "https://via.placeholder.com/48",
                    "alt_text": f"Imagen de {brand} {model}"
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

            register_interaction("rejected", {
                "sku": sku,
                "brand": brand,
                "model": model,
                "branch": branch,
                "user": user_display
            })

        except Exception as e:
            print(f"Error updating rejection message: {e}")

        response_text = f":x: Oferta rechazada para SKU {sku} por {user_display}."

    else:
        response_text = "Acción no reconocida."

    return PlainTextResponse(response_text)

@app.get("/")
async def home():
    return {"ok": True, "message": "Slack webhook activo"}
