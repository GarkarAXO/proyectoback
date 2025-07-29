import datetime
import time
import re
import os
import json
from collections import Counter
from dotenv import load_dotenv

load_dotenv()

from servicio_pse import clean_price_str
from notificador_slack import send_slack_notification, format_slack_message
from openai import OpenAI
from scraper_completo import obtener_imagenes_efectimundo

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

START_SEND_HOUR = 7
END_SEND_HOUR = 20
MIN_DOMINANT_FREQ = 3
MIN_PROFIT_THRESHOLD = 100.0
IMAGENES_CACHE_FILE = "imagenes_cache.json"

def analyze_offer_with_openai(product_data, comparison_data):
    prompt = f"""
Analiza la siguiente oferta de un producto en distintas sucursales y determina si vale la pena comprarlo para reventa.
Precio de sucursal: {product_data['Precio Promoción']}
Precio dominante (más repetido): {comparison_data['precio_dominante']}
Margen calculado: {comparison_data['margen']}
¿Es una buena oportunidad? Responde con 'Sí' o 'No' y justifica brevemente (máx 20 palabras).
"""
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
            temperature=0.5
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error OpenAI: {e}")
        return "Análisis no disponible."

def process_and_send_all_deals(all_scraped_products):
    print(f"--- Procesando y enviando ofertas de todas las tiendas ---")
    print(f"Total productos recibidos: {len(all_scraped_products)}")

    # Agrupar por modelo
    deals_by_model = {}
    for product in all_scraped_products:
        key = (product.get("Marca", "").strip(), product.get("Modelo", "").strip())
        deals_by_model.setdefault(key, []).append(product)

    final_deals_to_send = []

    for model_key, items in deals_by_model.items():
        if len(items) < 2:
            continue

        precios_promocion = [clean_price_str(p.get("Precio Promoción", "0")) for p in items]
        conteo = Counter(precios_promocion)
        precio_dominante, frecuencia = conteo.most_common(1)[0]

        if frecuencia < MIN_DOMINANT_FREQ:
            continue

        mejores_ofertas = []
        for p in items:
            precio = clean_price_str(p.get("Precio Promoción", "0"))
            if precio < precio_dominante:
                margen = precio_dominante - precio
                if margen >= MIN_PROFIT_THRESHOLD:
                    p["MargenCalculado"] = margen
                    mejores_ofertas.append(p)

        final_deals_to_send.extend(mejores_ofertas)

    print(f"Ofertas válidas encontradas: {len(final_deals_to_send)}")

    if not final_deals_to_send:
        print("No hay ofertas que cumplan las condiciones.")
        return

    final_deals_to_send.sort(key=lambda x: x["MargenCalculado"], reverse=True)

    now = datetime.datetime.now()
    end_of_day = now.replace(hour=END_SEND_HOUR, minute=0, second=0, microsecond=0)
    if now.hour >= END_SEND_HOUR:
        print("Fuera del horario permitido.")
        return

    tiempo_restante = (end_of_day - now).total_seconds()
    intervalo_envio = 180  # 3 minutos fijos entre envíos

    # Cargar caché si existe
    if os.path.exists(IMAGENES_CACHE_FILE):
        with open(IMAGENES_CACHE_FILE, "r") as f:
            imagenes_cache = json.load(f)
    else:
        imagenes_cache = {}

    for i, producto in enumerate(final_deals_to_send):
        print(f"Enviando {i+1}/{len(final_deals_to_send)}: {producto.get('Marca')} {producto.get('Modelo')}")

        model_key = (producto.get("Marca", ""), producto.get("Modelo", ""))
        precios_para_modelo = [
            clean_price_str(p.get("Precio Promoción", "0")) for p in deals_by_model.get(model_key, [])
        ]
        conteo = Counter(precios_para_modelo)
        precio_dominante, _ = conteo.most_common(1)[0]

        product_id = producto.get("Prenda / Sku Lote", "N/A")
        margen = producto.get("MargenCalculado", 0)

        # Buscar imágenes si no están en caché
        if product_id in imagenes_cache:
            producto["Imagenes"] = imagenes_cache[product_id]
        else:
            imagenes = obtener_imagenes_efectimundo(product_id)
            imagenes_cache[product_id] = imagenes
            producto["Imagenes"] = imagenes

        comparison_data = {
            "precio_dominante": precio_dominante,
            "margen": f"${margen:,.2f}",
            "product_id": product_id
        }

        ai_analysis = analyze_offer_with_openai(producto, comparison_data)
        comparison_data["openai_analysis"] = ai_analysis

        payload = format_slack_message(producto, comparison_data)
        send_slack_notification(payload)

        if i < len(final_deals_to_send) - 1:
            time.sleep(intervalo_envio)

    # Guardar caché actualizado al final
    with open(IMAGENES_CACHE_FILE, "w") as f:
        json.dump(imagenes_cache, f, indent=2)

    print("Proceso completado.")
