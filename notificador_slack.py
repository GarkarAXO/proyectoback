import os
import json
import urllib.request
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

def send_slack_notification(payload):
    """
    Envía un mensaje al webhook de Slack configurado con estructura de bloques.
    """
    if not SLACK_WEBHOOK_URL:
        print("Error: La URL del webhook de Slack no está configurada. Revisa tus variables de entorno.")
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
                print("Notificación de Slack enviada con éxito.")
            else:
                print(f"Error al enviar notificación a Slack: {response.status} {response.read().decode()}")

    except Exception as e:
        print(f"No se pudo enviar la notificación a Slack: {e}")

def format_slack_message(product, comparison_data):
    """
    Formatea el mensaje de la oferta para enviarlo a Slack usando blocks.
    """
    blocks = []

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f""":iphone: *Oferta de {product['Marca']} {product['Modelo']} encontrada!*
*Modelo:* {product['Modelo']}
*Sucursal:* {product['Tienda']}
*Descripción:* {product['Descripción']}
*Prenda/Lote:* {comparison_data['product_id']}
:moneybag: *Precio de sucursal:* {product['Precio Promoción']}
:moneybag: Precio dominante (modelo): ${comparison_data['precio_dominante']:,.2f}
💵 *Margen estimado:* {comparison_data['margen']}"""
        }
    })

    # Agregar imagen si existe
    imagenes = product.get("Imagenes", [])
    if imagenes and isinstance(imagenes[0], str) and imagenes[0].startswith("http"):
        blocks.append({
            "type": "image",
            "image_url": imagenes[0],
            "alt_text": f"Imagen de {product['Marca']} {product['Modelo']}"
        })

    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"🤖 *Análisis IA:* {comparison_data['openai_analysis']}"
            }
        ]
    })

    blocks.append({ "type": "divider" })

    return { "blocks": blocks }