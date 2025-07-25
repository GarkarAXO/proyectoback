import os
import json
import urllib.request
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

def send_slack_notification(message):
    """
    Envía un mensaje al webhook de Slack configurado.
    """
    if not SLACK_WEBHOOK_URL:
        print("Error: La URL del webhook de Slack no está configurada. Revisa tus variables de entorno.")
        return

    try:
        payload = {'text': message}
        data = json.dumps(payload).encode('utf-8')
        
        req = urllib.request.Request(
            SLACK_WEBHOOK_URL, 
            data=data, 
            headers={'Content-Type': 'application/json'}
        )
        
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                print("Notificación de Slack enviada con éxito.")
            else:
                print(f"Error al enviar notificación a Slack: {response.status} {response.read().decode()}")

    except Exception as e:
        print(f"No se pudo enviar la notificación a Slack: {e}")

def format_slack_message(product_data, comparison_data):
    """
    Formatea el mensaje de la oferta para enviarlo a Slack.
    """
    return f"""
:iphone: *¡Oferta de {product_data['Marca']} {product_data['Modelo']} encontrada!*
Producto: {product_data['Marca']} {product_data['Modelo']}
Sucursal: {product_data['Tienda']}
Descripción: {product_data['Descripción']}
Estimación de Precios de Mercado (MXN):
🌎 *Precio en Efectimundo: {product_data['Precio Venta']}*
♻️ Precio Reacondicionados (Estimado): {comparison_data['reacondicionados']}
🆕 Precio de Nuevos (Estimado): {comparison_data['nuevos']}
💵 *Margen aproximado: {comparison_data['margen']}*
"""
