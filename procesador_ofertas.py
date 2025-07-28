import datetime
import time
import re
import openai
import os
from dotenv import load_dotenv

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

from servicio_pse import clean_price_str
from notificador_slack import send_slack_notification, format_slack_message

START_SEND_HOUR = 7
END_SEND_HOUR = 20

MIN_UNITS_FOR_MARGIN_CALCULATION = 3 # Mínimo de unidades del mismo modelo para calcular margen
MIN_PROFIT_THRESHOLD = 100.0 # Margen mínimo en MXN para considerar una oferta

def analyze_offer_with_openai(product_data, comparison_data):
    prompt = f"""
Analiza la siguiente oferta de un producto de Efectimundo y determina si 'vale la pena' comprarlo para reventa, basándote en los datos proporcionados. Sé conciso y responde solo 'Sí', 'No' o 'Podría ser', seguido de una breve justificación (máximo 20 palabras).

Datos de la oferta:
Producto: {product_data['Marca']} {product_data['Modelo']}
Precio en Efectimundo: {product_data['Precio Venta']}
Margen calculado: {comparison_data['margen']}
Mayor precio en Efectimundo (modelo): ${comparison_data['mayor_precio_efectimundo']:,.2f}
Menor precio en Efectimundo (modelo): ${comparison_data['menor_precio_efectimundo']:,.2f}

¿Vale la pena esta oferta para reventa?
"""

    try:
        if not openai.api_key:
            raise ValueError("OPENAI_API_KEY no configurada.")

        response = openai.completions.create(
            model="gpt-3.5-turbo-instruct", # O el modelo que prefieras para completions
            prompt=prompt,
            max_tokens=50,
            temperature=0.5
        )
        return response.choices[0].text.strip()
    except ValueError as ve:
        print(f"Advertencia: {ve}. No se realizará el análisis de IA.")
        return "Análisis de IA no disponible (API Key no configurada)"
    except Exception as e:
        print(f"Error al llamar a OpenAI: {e}")
        return "Análisis de IA no disponible (Error de IA)"

def process_and_send_all_deals(all_scraped_products):
    print(f"\n--- Procesando y enviando ofertas de todas las tiendas ---")
    print(f"DEBUG: all_scraped_products recibido: {len(all_scraped_products)} items.")

    interest_keywords = {
        'CONSOLAS DE JUEGOS': [
            'ps5', 'ps4', 'playstation 5', 'playstation 4', 'xbox series x', 'xbox series s', 'nintendo switch'
        ],
        'JUEGOS DE VIDEO': [
            'ps5', 'ps4', 'xbox', 'nintendo', 'switch', 'fifa', 'call of duty', 'mario', 'zelda', 'elden ring'
        ],
        'ACCESORIOS DE CONSOLAS': [
            'control', 'mando', 'headset', 'volante', 'vr', 'realidad virtual', 'dock', 'cargador'
        ],
        'SMARTWATCH': [
            'apple watch', 'galaxy watch', 'garmin', 'watch ultra', 'fitbit', 'huawei watch'
        ],
        'AUDIFONOS': [
            'airpods pro', 'airpods max', 'sony wh-1000', 'bose', 'sennheiser', 'beats studio', 'quietcomfort', 'galaxy buds pro', 'jbl', 'marshall'
        ],
        'PANTALLAS': [
            'oled', 'qled', '4k', '8k', 'smart tv', 'samsung', 'lg', 'sony', 'hisense', 'tcl'
        ],
        'PROYECTORES': [
            '4k', 'hd', 'tiro corto', 'laser', 'epson', 'benq', 'optoma', 'lg cinebeam'
        ],
        'LAPTOP Y MINI LAPTOP': [
            'core i7', 'core i9', 'ryzen 7', 'ryzen 9', 'rtx', 'quadro', 'macbook pro', 'macbook air', 'xps', 'surface', 'zenbook', 'core i5', 'ryzen 5', 'gtx'
        ],
        'PC ESCRITORIO': [
            'core i7', 'core i9', 'ryzen 7', 'ryzen 9', 'rtx', 'gtx', 'gaming', 'alienware', 'omen', 'rog'
        ],
        'MONITORES': [
            '4k', '144hz', 'curvo', 'ultrawide', 'oled', 'qled', 'gaming', 'dell', 'lg', 'samsung', 'asus'
        ],
        'TABLETAS': [
            'ipad pro', 'ipad air', 'galaxy tab s', 'surface pro', 'lenovo tab', 'xiaomi pad'
        ],
        'CELULARES': [
            'pro', 'max', 'ultra', 'fold', 'flip', 'edge', 'snapdragon 8', 'snapdragon 7', 'iphone 11', 'iphone 12', 'iphone 13', 'iphone 14', 'iphone 15', 'galaxy s2', 'galaxy z', 'pixel', 'oneplus', 'xiaomi', 'huawei p', 'galaxy a'
        ]
    }

    filtered_deals = []
    for product_dict in all_scraped_products:
        if "dañado" in product_dict.get('Descripción', '').lower():
            continue

        familia_clean = product_dict.get('Familia', '').split('(')[0].strip()

        if familia_clean in interest_keywords:
            search_text = (
                product_dict.get('Marca', '') + ' ' +
                product_dict.get('Modelo', '') + ' ' +
                product_dict.get('Descripción', '')
            ).lower()

            for keyword in interest_keywords[familia_clean]:
                if keyword in search_text:
                    filtered_deals.append(product_dict)
                    break
    print(f"DEBUG: filtered_deals (después de filtros): {len(filtered_deals)} items.")

    if not filtered_deals:
        print(f"No se encontraron ofertas de interés en ninguna tienda.")
        return

    # Agrupar ofertas por modelo para el cálculo de margen
    deals_by_model_for_margin = {}
    for deal in filtered_deals:
        model_key = (deal.get('Marca', 'N/A'), deal.get('Modelo', 'N/A'))
        if model_key not in deals_by_model_for_margin:
            deals_by_model_for_margin[model_key] = []
        deals_by_model_for_margin[model_key].append(deal)
    print(f"DEBUG: deals_by_model_for_margin (agrupados por modelo): {len(deals_by_model_for_margin)} modelos.")

    # Calcular el margen para cada oferta y seleccionar las mejores
    final_deals_to_send = []
    for model_key, deals_list in deals_by_model_for_margin.items():
        # Solo procesar modelos con suficientes unidades para un cálculo de margen significativo
        if len(deals_list) < MIN_UNITS_FOR_MARGIN_CALCULATION:
            continue

        # Ordenar por precio de venta de menor a mayor para identificar las ofertas
        deals_list.sort(key=lambda p: clean_price_str(p.get('Precio Venta', '0')))

        for i, current_deal in enumerate(deals_list):
            current_price = clean_price_str(current_deal.get('Precio Venta', '0'))

            # Encontrar precios de unidades más caras del mismo modelo
            higher_priced_units = [
                clean_price_str(d.get('Precio Venta', '0'))
                for d in deals_list
                if clean_price_str(d.get('Precio Venta', '0')) > current_price
            ]

            margen_calculado = 0.0
            if higher_priced_units:
                average_higher_price = sum(higher_priced_units) / len(higher_priced_units)
                margen_calculado = average_higher_price - current_price

            # Solo añadir la oferta si el margen calculado es significativo
            if margen_calculado >= MIN_PROFIT_THRESHOLD:
                current_deal['MargenCalculado'] = margen_calculado
            final_deals_to_send.append(current_deal)
    print(f"DEBUG: final_deals_to_send (con margen calculado): {len(final_deals_to_send)} items.")

    # Seleccionar los 3 mejores de cada modelo (ahora con margen calculado)
    # Primero, agrupar por modelo nuevamente, pero ahora con el margen calculado
    deals_by_model_for_top_selection = {}
    for deal in final_deals_to_send:
        model_key = (deal.get('Marca', 'N/A'), deal.get('Modelo', 'N/A'))
        if model_key not in deals_by_model_for_top_selection:
            deals_by_model_for_top_selection[model_key] = []
        deals_by_model_for_top_selection[model_key].append(deal)

    top_deals = []
    for model_key, deals_list in deals_by_model_for_top_selection.items():
        print(f"DEBUG: Inspecting deals_list for model {model_key} before sort (length: {len(deals_list)}):")
        for item_in_list in deals_list:
            print(f"DEBUG:   Item keys: {item_in_list.keys()}")
            if 'MargenCalculado' not in item_in_list:
                print(f"DEBUG:   !!! PROBLEM: Item is missing 'MargenCalculado' !!!: {item_in_list}")
        # Ordenar por margen (mayor a menor) y luego por precio (menor a mayor)
       # Filtrar solo los productos que tienen MargenCalculado
        deals_with_margin = [p for p in deals_list if 'MargenCalculado' in p]
        if not deals_with_margin:
            print(f"DEBUG:   No deals with MargenCalculado for model {model_key}. Skipping.")
            continue

        # Ordenar por margen (mayor a menor) y luego por precio (menor a mayor)
        deals_with_margin.sort(
            key=lambda p: (p['MargenCalculado'], -clean_price_str(p.get('Precio Venta', '0'))),
            reverse=True
        )
        top_deals.extend(deals_with_margin[:3])
    print(f"DEBUG: top_deals (final antes de retornar): {len(top_deals)} items.")
    print(f"DEBUG: top_deals (final antes de retornar): {len(top_deals)} items.")

    if not top_deals:
        print("No se encontraron ofertas válidas para enviar.")
        return

    # Ordenar la lista final por margen para enviar las mejores primero
    top_deals.sort(key=lambda p: p['MargenCalculado'], reverse=True)

    now = datetime.datetime.now()
    end_of_day = now.replace(hour=END_SEND_HOUR, minute=0, second=0, microsecond=0)
    if now.hour >= END_SEND_HOUR:
        print("Fuera del horario de envío de mensajes.")
        return

    time_left_seconds = (end_of_day - now).total_seconds()
    min_interval_seconds = 4 * 60 # 4 minutos
    num_deals_to_send = len(top_deals)

    ideal_interval = time_left_seconds / num_deals_to_send if num_deals_to_send > 0 else min_interval_seconds
    send_interval = max(min_interval_seconds, ideal_interval)

    print(f"Se encontraron {num_deals_to_send} ofertas de interés. Enviando cada {send_interval:.0f} segundos.")

    for i, product in enumerate(top_deals):
        print(f"Enviando oferta {i+1}/{num_deals_to_send}...")

        # Obtener mayor y menor precio de Efectimundo para este modelo
        model_key = (product.get('Marca', 'N/A'), product.get('Modelo', 'N/A'))
        prices_for_this_model = [
            clean_price_str(d.get('Precio Venta', '0')) 
            for d in filtered_deals 
            if (d.get('Marca', 'N/A'), d.get('Modelo', 'N/A')) == model_key
        ]
        
        mayor_precio_efectimundo = max(prices_for_this_model) if prices_for_this_model else 0.0
        menor_precio_efectimundo = min(prices_for_this_model) if prices_for_this_model else 0.0

        # Extraer ID/SKU (Prenda/Lote)
        product_id = product.get('Prenda / Sku Lote', 'N/A')

        comparison_data = {
            'reacondicionados': 'N/A',
            'nuevos': 'N/A',
            'margen': f"${product['MargenCalculado']:,.2f}",
            'mayor_precio_efectimundo': mayor_precio_efectimundo,
            'menor_precio_efectimundo': menor_precio_efectimundo,
            'product_id': product_id
        }

        # Analizar la oferta con OpenAI
        openai_analysis = analyze_offer_with_openai(product, comparison_data)
        comparison_data['openai_analysis'] = openai_analysis

        message = format_slack_message(product, comparison_data)
        send_slack_notification(message)

        if i < num_deals_to_send - 1:
            time.sleep(send_interval)

    print(f"Envío de ofertas completado.")