import os
import json
import time
from datetime import date
from dotenv import load_dotenv
from full_scraper import get_images_by_sku
from slack_sdk import WebClient

load_dotenv()
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
client = WebClient(token=SLACK_BOT_TOKEN)

# State file for the rotating store queue
STATE_FILE = "store_queue_state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            state = json.load(open(STATE_FILE, "r", encoding="utf-8"))
            # Ensure sent_skus_today is initialized
            if "sent_skus_today" not in state:
                state["sent_skus_today"] = []
            # Ensure new fields are initialized
            if "notification_completed_today" not in state:
                state["notification_completed_today"] = False
            if "last_notification_date" not in state:
                state["last_notification_date"] = "1970-01-01"
            return state
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Error loading state file or file is empty, re-initializing. Error: {e}")
    return {"current_start_index": -3, "last_update_date": "1970-01-01", "sent_skus_today": [], "notification_completed_today": False, "last_notification_date": "1970-01-01"}

def save_state(data):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving state: {e}")

# Load sorting config
try:
    with open("config_orden_envio.json", "r", encoding="utf-8") as f:
        send_order_config = json.load(f)
    SORTED_FAMILIES = send_order_config.get("familias_ordenadas", [])
    SORTED_BRANCHES_MAP = send_order_config.get("sucursales_ordenadas", {})
    SORTED_BRANCHES_LIST = list(SORTED_BRANCHES_MAP.values())
    SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID") or "TU_CHANNEL_ID"
except Exception as e:
    SORTED_FAMILIES = []
    SORTED_BRANCHES_LIST = []
    SLACK_CHANNEL_ID = ""
    print(f"Advertencia al cargar el orden de envío: {e}")

# IA desactivada temporalmente
def analyze_offer_with_openai(product_data, model_products):
    return "Sí\nMotivo: IA desactivada temporalmente"

def format_slack_blocks(brand, model, item, q1, q3,
                        low_range_count, low_range_str,
                        dominant_count, high_range_count, high_range_str,
                        channel_id, message_ts,
                        openai_msg=None):
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":iphone: *¡Oferta detectada!*\n"
                    f"*Marca:* {brand}\n"
                    f"*Modelo:* {model}\n"
                    f"*Prenda/SKU:* {item['SKU']}\n"
                    f"*Descripción:* {item['Descripción']}\n"
                    f"*Sucursal:* {item['Sucursal']}\n"
                    f"*Precio en sucursal:* {item['Precio Promoción']}\n"
                    f":dollar: *Margen estimado:* ${item.get('MargenVsDominanteMenor', 0):,.0f}\n"
                    f":label: *Artículo en rango bajo ({low_range_count}):* {low_range_str}\n"
                    f":moneybag: *Rango de precio dominante ({dominant_count}):* ${q1:,.0f} a ${q3:,.0f}\n"
                    f":chart_with_upwards_trend: *Rango alto ({high_range_count}):* {high_range_str}"
                )
            }
        }
    ]

    image_url = None
    if "Imagenes" in item and isinstance(item["Imagenes"], list) and item["Imagenes"]:
        image_url = item["Imagenes"][0]
        if not (isinstance(image_url, str) and image_url.startswith("http")):
            image_url = None
    if not image_url:
        sku = item.get("SKU", "")
        images = get_images_by_sku(sku)
        if images and images[0].startswith("http"):
            image_url = images[0]
    if image_url:
        blocks.append({
            "type": "image",
            "image_url": image_url,
            "alt_text": f"Imagen de {brand} {model}"
        })

    buttons_value = {
        "sku": item["SKU"],
        "marca": brand,
        "modelo": model,
        "channel_id": channel_id,
        "message_ts": message_ts
    }
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "✅ Aceptar oferta"},
                "style": "primary",
                "action_id": "aceptar_oferta",
                "value": json.dumps(buttons_value)
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "❌ Rechazar"},
                "style": "danger",
                "action_id": "rechazar_oferta",
                "value": json.dumps(buttons_value)
            }
        ]
    })

    if openai_msg:
        parts = openai_msg.split("\n", 1)
        decision = parts[0].strip()
        reason = parts[1].strip() if len(parts) > 1 else ""
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"🤖 *Análisis IA:* *{decision}*\n_{reason}_"
            }
        })

    blocks.append({"type": "divider"})
    return blocks

def sort_key(item):
    family = item.get("Familia", "")
    branch = item.get("Sucursal", "")
    price = float(item.get("Precio Promoción", "0").replace("$", "").replace(",", "") or 0)
    family_idx = SORTED_FAMILIES.index(family) if family in SORTED_FAMILIES else len(SORTED_FAMILIES)
    branch_idx = SORTED_BRANCHES_LIST.index(branch) if branch in SORTED_BRANCHES_LIST else len(SORTED_BRANCHES_LIST)
    return (family_idx, branch_idx, price)

def send_slack_notification(payload_blocks):
    if not SLACK_CHANNEL_ID:
        print("Error: SLACK_CHANNEL_ID no configurado.")
        return None
    try:
        response = client.chat_postMessage(
            channel=SLACK_CHANNEL_ID,
            text="¡Oferta detectada!",
            blocks=payload_blocks
        )
        return response.get("ts")
    except Exception as e:
        print("No se pudo enviar la notificación a Slack (bot):", e)
        return None

def notify_detected_bargains(path_analysis="model_analysis.json", model_products_path="grouped_products_by_model.json"):
    state = load_state()
    today_str = str(date.today())
    
    current_index = state.get("current_start_index", -3)
    last_update = state.get("last_update_date", "1970-01-01")
    
    # New fields
    notification_completed_today = state.get("notification_completed_today", False)
    last_notification_date = state.get("last_notification_date", "1970-01-01")

    if today_str != last_update:
        print(f"Nuevo día detectado. Avanzando índice de sucursales y reiniciando SKUs enviados.")
        current_index = (current_index + 3)
        if current_index >= len(SORTED_BRANCHES_LIST):
            current_index = 0 # Reset to the beginning
        
        state = {"current_start_index": current_index, "last_update_date": today_str, "sent_skus_today": [], "notification_completed_today": False, "last_notification_date": today_str}
        save_state(state)
    else:
        # Ensure sent_skus_today is loaded correctly for the current day
        if "sent_skus_today" not in state:
            state["sent_skus_today"] = []
        # Ensure new fields are loaded correctly for the current day
        if "notification_completed_today" not in state:
            state["notification_completed_today"] = False
        if "last_notification_date" not in state:
            state["last_notification_date"] = today_str


    # Determine the 3 stores for today
    stores_for_today = []
    if not SORTED_BRANCHES_LIST:
        print("Error: La lista de sucursales ordenadas está vacía.")
        return

    start_index = current_index
    for i in range(3):
        # Ensure the index wraps around correctly
        idx = (start_index + i) % len(SORTED_BRANCHES_LIST)
        stores_for_today.append(SORTED_BRANCHES_LIST[idx])
    
    print(f"Sucursales para procesar hoy ({today_str}): {stores_for_today}")

    # Load product data
    try:
        with open(model_products_path, "r", encoding="utf-8") as f:
            model_products = json.load(f)
        with open(path_analysis, "r", encoding="utf-8") as f:
            analysis = json.load(f)
    except FileNotFoundError as e:
        print(f"Error: No se encontró el archivo {e.filename}. Saltando ciclo de notificación.")
        return

    items_to_send = []
    for model_key, info in analysis.items():
        brand, model = model_key.split("::", 1) if "::" in model_key else ("", model_key)

        q1 = info.get("q1", 0)
        q3 = info.get("q3", 0)
        products = model_products.get(model_key, [])

        top_offers = info.get("top_5_mas_baratos") or info.get("top_4_mas_baratos", [])
        if not top_offers or not products:
            continue

        min_price = float(top_offers[0]["Precio Promoción"].replace("$", "").replace(",", ""))
        low_range_str = f"${min_price:,.0f} a ${q1:,.0f}"
        low_range_count = sum(min_price <= float(p["Precio Promoción"].replace("$", "").replace(",", "")) <= q1 for p in products)
        dominant_count = sum(q1 <= float(p["Precio Promoción"].replace("$", "").replace(",", "")) <= q3 for p in products)
        max_price = max(float(p["Precio Promoción"].replace("$", "").replace(",", "")) for p in products) if products else 0
        high_range_str = f"${q3:,.0f} a ${max_price:,.0f}"
        high_range_count = sum(q3 < float(p["Precio Promoción"].replace("$", "").replace(",", "")) <= max_price for p in products)

        for article in top_offers:
            items_to_send.append({
                "brand": brand,
                "model": model,
                "item": article,
                "q1": q1,
                "q3": q3,
                "low_range_count": low_range_count,
                "low_range_str": low_range_str,
                "dominant_count": dominant_count,
                "high_range_count": high_range_count,
                "high_range_str": high_range_str,
                "model_products": products
            })

    # Filter items for today's stores
    filtered_items = [i for i in items_to_send if i["item"]["Sucursal"] in stores_for_today]
    
    # Sort the filtered items
    filtered_items.sort(key=lambda x: sort_key(x["item"]))

    print(f"Se van a enviar {len(filtered_items)} ofertas a Slack para las sucursales de hoy.")

    sent_count = 0
    for item in filtered_items:
        sku = item["item"]["SKU"]
        if sku in state["sent_skus_today"]:
            print(f"SKU {sku} ya enviado hoy. Saltando.")
            continue

        openai_msg = analyze_offer_with_openai(item["item"], item["model_products"])
        if not openai_msg.lower().startswith("sí") and not openai_msg.lower().startswith("si"):
            continue

        temp_blocks = format_slack_blocks(
            brand=item["brand"], model=item["model"], item=item["item"],
            q1=item["q1"], q3=item["q3"],
            low_range_count=item["low_range_count"], low_range_str=item["low_range_str"],
            dominant_count=item["dominant_count"], high_range_count=item["high_range_count"],
            high_range_str=item["high_range_str"], channel_id=SLACK_CHANNEL_ID, message_ts=""
        )
        message_ts = send_slack_notification(temp_blocks)
        if not message_ts:
            continue

        final_blocks = format_slack_blocks(
            brand=item["brand"], model=item["model"], item=item["item"],
            q1=item["q1"], q3=item["q3"],
            low_range_count=item["low_range_count"], low_range_str=item["low_range_str"],
            dominant_count=item["dominant_count"], high_range_count=item["high_range_count"],
            high_range_str=item["high_range_str"], channel_id=SLACK_CHANNEL_ID, message_ts=message_ts,
            openai_msg=openai_msg
        )
        try:
            client.chat_update(channel=SLACK_CHANNEL_ID, ts=message_ts, text="¡Oferta detectada!", blocks=final_blocks)
        except Exception as e:
            print(f"Error al actualizar mensaje: {e}")

        sent_count += 1
        state["sent_skus_today"].append(sku) # Add SKU to sent list
        save_state(state) # Save state after sending each item
        print(f"Oferta enviada: {item['brand']} {item['model']} ({item['item']['Sucursal']}) - Esperando 3 minutos...")
        time.sleep(180)

    # At the end of the function, after all items have been processed
    state["notification_completed_today"] = True
    state["last_notification_date"] = today_str # Ensure this is updated
    save_state(state)

    print(f"Ofertas totales enviadas hoy ({today_str}): {sent_count} | Sucursales procesadas: {stores_for_today}")


if __name__ == "__main__":
    notify_detected_bargains()
