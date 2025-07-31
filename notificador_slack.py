import os
import json
import time
import urllib.request
from dotenv import load_dotenv
from scraper_completo import obtener_imagenes_efectimundo

# Cargar variables de entorno
load_dotenv()
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

def send_slack_notification(payload):
    if not SLACK_WEBHOOK_URL:
        print("Error: SLACK_WEBHOOK_URL no configurada en .env")
        return

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            SLACK_WEBHOOK_URL,
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                print("Notificación enviada a Slack")
            else:
                print(f"Error al enviar notificación: {response.status} {response.read().decode()}")
    except Exception as e:
        print(f"No se pudo enviar la notificación a Slack: {e}")

def format_slack_message(marca, modelo, articulo, q1, q3):
    blocks = []
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": (
                f":star: *¡Oferta detectada!*\n"
                f"*Marca:* {marca}\n"
                f"*Modelo:* {modelo}\n"
                f"*Prenda/SKU:* {articulo['SKU']}\n"
                f"*Precio en sucursal:* {articulo['Precio Promoción']}\n"
                f"*Descripción:* {articulo['Descripción']}\n"
                f"*Sucursal:* {articulo['Sucursal']}\n"
                f":moneybag: *Rango de precio dominante:* ${q1:,.0f} a ${q3:,.0f}\n"
                f":dollar: *Margen estimado:* ${articulo['MargenVsDominanteMenor']:,.0f}"
            )
        }
    })

    # Imagen: del JSON o en vivo si hace falta
    img_url = None
    if "Imagenes" in articulo and isinstance(articulo["Imagenes"], list) and articulo["Imagenes"]:
        img_url = articulo["Imagenes"][0]
        if not (isinstance(img_url, str) and img_url.startswith("http")):
            img_url = None

    if not img_url:
        sku = articulo.get("SKU", "")
        imagenes = obtener_imagenes_efectimundo(sku)
        if imagenes and isinstance(imagenes, list) and imagenes[0].startswith("http"):
            img_url = imagenes[0]

    if img_url:
        blocks.append({
            "type": "image",
            "image_url": img_url,
            "alt_text": f"Imagen de {marca} {modelo}"
        })

    blocks.append({"type": "divider"})
    return {"blocks": blocks}

def notificar_gangas_encontradas(path_analisis="analisis_modelos.json"):
    with open(path_analisis, "r", encoding="utf-8") as f:
        analisis = json.load(f)
    ofertas_enviadas = 0

    for modelo_key, info in analisis.items():
        # Obtén marca y modelo
        if "::" in modelo_key:
            marca, modelo = modelo_key.split("::", 1)
        else:
            marca, modelo = "", modelo_key

        q1 = info.get("q1", 0)
        q3 = info.get("q3", 0)

        for articulo in info["top_4_mas_baratos"]:
            payload = format_slack_message(
                marca=marca,
                modelo=modelo,
                articulo=articulo,
                q1=q1,
                q3=q3
            )
            send_slack_notification(payload)
            ofertas_enviadas += 1
            print(f"Oferta de {marca} {modelo} enviada a Slack. Esperando 3 minutos...")
            time.sleep(180)  # Espera 3 minutos entre mensajes

    print(f"Ofertas totales enviadas a Slack: {ofertas_enviadas}")

