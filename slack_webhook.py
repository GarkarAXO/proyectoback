import os
import json
from datetime import date
from dotenv import load_dotenv
from slack_sdk import WebClient
from fastapi import FastAPI, Form
from fastapi.responses import PlainTextResponse
from pyngrok import ngrok
import uvicorn

# ====== CONFIG ENV ======
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

# ====== FUNCIONES ======
def get_user_display_name(user_info: dict) -> str:
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
    log_data[today][action_type].append(data_item)
    with open(INTERACTION_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)

# ====== RUTAS ======
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
            updated_blocks = [
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f":white_check_mark: *Oferta aceptada por* `{user_display}`"
                        }
                    ]
                } if block.get("type") == "actions" else block
                for block in original_blocks
            ]
            client.chat_update(
                channel=channel_id,
                ts=message_ts,
                text=f"Oferta aceptada por {user_display}",
                blocks=updated_blocks
            )
            register_interaction("accepted", {
                "sku": sku, "brand": brand, "model": model, "branch": branch, "user": user_display
            })
        except Exception as e:
            print(f"Error updating Slack message: {e}")
        response_text = f":white_check_mark: ¡Oferta aceptada para SKU {sku} por {user_display}!"

    elif action_id == "rechazar_oferta":
        try:
            original_blocks = data.get("message", {}).get("blocks", [])
            img_url = None
            description = None
            for block in original_blocks:
                if block.get("type") == "image" and block.get("image_url"):
                    img_url = block.get("image_url")
                elif block.get("type") == "section" and "text" in block:
                    text = block["text"]["text"]
                    lines = text.split("\n")
                    desc_line = next((l.replace("*Descripción:*", "").strip()
                                      for l in lines if "*Descripción:*" in l), "")
                    if desc_line:
                        description = desc_line
            updated_blocks = [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn",
                             "text": f"*Prenda/SKU:* {sku}\n*Descripción:* {description or ''}"},
                    "accessory": {
                        "type": "image",
                        "image_url": img_url or "https://via.placeholder.com/48",
                        "alt_text": f"Imagen de {brand} {model}"
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f":x: *Oferta rechazada por* `{user_display}`"
                        }
                    ]
                }
            ]
            client.chat_update(
                channel=channel_id,
                ts=message_ts,
                text=f"Oferta rechazada por {user_display}",
                blocks=updated_blocks
            )
            register_interaction("rejected", {
                "sku": sku, "brand": brand, "model": model, "branch": branch, "user": user_display
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

# ====== MAIN ======
if __name__ == "__main__":
    PORT = 8000

    # Iniciar túnel ngrok
    public_url = ngrok.connect(PORT)
    print(f"\n[NGROK] URL pública: {public_url}")
    print(f"[INFO] Configura Slack con: {public_url}/slack/interactivity\n")

    # Levantar servidor
    uvicorn.run("slack_webhook:app", host="0.0.0.0", port=PORT, reload=False)
