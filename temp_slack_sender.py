

import json
import urllib.request
import urllib.parse

# URL del Webhook de Slack
SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/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"

def send_slack_notification(message):
    """
    Envía un mensaje al webhook de Slack configurado.
    """
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

def send_comparison_to_slack(product_data, comparison_data):
    message = f"""
:iphone: *¡Oferta de {product_data['Marca']} {product_data['Modelo']} encontrada!*\nProducto: {product_data['Marca']} {product_data['Modelo']}\nSucursal: {product_data['Tienda']}\nDescripción: {product_data['Descripción']}\nComparación de Mercado (precios aproximados en MXN):\n:earth_americas: Precio en Efectimundo: *{product_data['Precio Venta']}*\n:recycle: Precio Reacondicionados (eBay, Mercado Libre, CEX): {comparison_data['reacondicionados']}\n:new: Precio de Nuevos: {comparison_data['nuevos']}\n:dollar: Margen aproximado: *{comparison_data['margen']}*
"""
    send_slack_notification(message)

# Datos del producto y comparación
product_data = {
    'Marca': 'APPLE',
    'Modelo': 'IPHONE 14 PRO MAX (A2893)-MEM:128GB',
    'Tienda': 'Texcoco Fray Pedro de Gante',
    'Descripción': 'CELULAR APPLE IPHONE 14 PRO MAX (A2893)-MEM:128GB-COM:TELCEL-IMEI:**********00839 COLOR MORADO CON FUNDA BLANCA Y CABLE DE CARGA GENERICO CON EL91% DE BATERIA DETALLES DE USO FUNCIONADO',
    'Precio Venta': '$ 10,100.00'
}
comparison_data = {
    'reacondicionados': 'Desde $12,000 hasta $15,000.',
    'nuevos': 'Desde $24,000 hasta $28,000.',
    'margen': '$1,900 hasta $4,900 (comparado con reacondicionados)'
}

# Llamar a la función para enviar el mensaje
send_comparison_to_slack(product_data, comparison_data)
