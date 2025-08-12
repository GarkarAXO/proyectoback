import os
import json
import time
from dotenv import load_dotenv
from full_scraper import get_images_by_sku
from slack_sdk import WebClient

load_dotenv()
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
client = WebClient(token=SLACK_BOT_TOKEN)

# Cargar configuración de ordenamiento para familias y sucursales
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
    try:
        with open(model_products_path, "r", encoding="utf-8") as f:
            model_products = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"No se pudo leer o decodificar {model_products_path}. No hay nada que notificar.")
        return

    try:
        with open(path_analysis, "r", encoding="utf-8") as f:
            analysis = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"No se pudo leer o decodificar {path_analysis}. No hay nada que notificar.")
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
        max_price = max(float(p["Precio Promoción"].replace("$", "").replace(",", "")) for p in products)
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

    # Ordenar todas las ofertas encontradas según la configuración
    items_to_send.sort(key=lambda x: sort_key(x["item"]))

    if not items_to_send:
        print("No se encontraron ofertas para notificar en esta ejecución.")
        return

    print(f"Se encontraron {len(items_to_send)} ofertas para notificar. Enviando una cada 3 minutos.")
    
    sent_count = 0
    for item in items_to_send:
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
        print(f"Notificación {sent_count}/{len(items_to_send)} enviada para: {item['brand']} {item['model']} en {item['item']['Sucursal']}")

        if sent_count < len(items_to_send):
            print("Esperando 3 minutos para la siguiente oferta...")
            time.sleep(180)

    print(f"Proceso de notificación finalizado. Se enviaron {sent_count} alertas.")