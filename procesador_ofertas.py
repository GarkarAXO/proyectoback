import datetime
import time
from servicio_pse import clean_price_str
from notificador_slack import send_slack_notification, format_slack_message

START_SEND_HOUR = 7
END_SEND_HOUR = 20

def get_top_deals_from_all_products(all_scraped_products):
    print(f"\n--- Procesando ofertas de todas las tiendas ---")

    top_deals = [] # Inicializar top_deals aquí

    # Horario de operación para el envío de mensajes (en horas, formato 24h)START_SEND_HOUR = 7END_SEND_HOUR = 20def process_and_send_deals_for_store(all_scraped_products, _):    print(f"\n--- Procesando y enviando ofertas de todas las tiendas ---")    interest_keywords = {        'CONSOLAS DE JUEGOS': [            'ps5', 'ps4', 'playstation 5', 'playstation 4', 'xbox series x', 'xbox series s', 'nintendo switch'        ],        'JUEGOS DE VIDEO': [            'ps5', 'ps4', 'xbox', 'nintendo', 'switch', 'fifa', 'call of duty', 'mario', 'zelda', 'elden ring'        ],        'ACCESORIOS DE CONSOLAS': [            'control', 'mando', 'headset', 'volante', 'vr', 'realidad virtual', 'dock', 'cargador'        ],        'SMARTWATCH': [            'apple watch', 'galaxy watch', 'garmin', 'watch ultra', 'fitbit', 'huawei watch'        ],        'AUDIFONOS': [            'airpods pro', 'airpods max', 'sony wh-1000', 'bose', 'sennheiser', 'beats studio', 'quietcomfort', 'galaxy buds pro', 'jbl', 'marshall'        ],        'PANTALLAS': [            'oled', 'qled', '4k', '8k', 'smart tv', 'samsung', 'lg', 'sony', 'hisense', 'tcl'        ],        'PROYECTORES': [            '4k', 'hd', 'tiro corto', 'laser', 'epson', 'benq', 'optoma', 'lg cinebeam'        ],        'LAPTOP Y MINI LAPTOP': [            'core i7', 'core i9', 'ryzen 7', 'ryzen 9', 'rtx', 'quadro', 'macbook pro', 'macbook air', 'xps', 'surface', 'zenbook', 'core i5', 'ryzen 5', 'gtx'        ],        'PC ESCRITORIO': [            'core i7', 'core i9', 'ryzen 7', 'ryzen 9', 'rtx', 'gtx', 'gaming', 'alienware', 'omen', 'rog'        ],        'MONITORES': [            '4k', '144hz', 'curvo', 'ultrawide', 'oled', 'qled', 'gaming', 'dell', 'lg', 'samsung', 'asus'        ],        'TABLETAS': [            'ipad pro', 'ipad air', 'galaxy tab s', 'surface pro', 'lenovo tab', 'xiaomi pad'        ],        'CELULARES': [            'pro', 'max', 'ultra', 'fold', 'flip', 'edge', 'snapdragon 8', 'snapdragon 7', 'iphone 11', 'iphone 12', 'iphone 13', 'iphone 14', 'iphone 15', 'galaxy s2', 'galaxy z', 'pixel', 'oneplus', 'xiaomi', 'huawei p', 'galaxy a'        ]    }    filtered_deals = []    for product_dict in all_scraped_products:        if "dañado" in product_dict.get('Descripción', '').lower():            print(f"DEBUG: Producto omitido por contener 'dañado' en la descripción: {product_dict.get('Marca')} {product_dict.get('Modelo')}")            continue        familia_clean = product_dict.get('Familia', '').split('(')[0].strip()        if familia_clean in interest_keywords:            search_text = (                product_dict.get('Marca', '') + ' ' +                 product_dict.get('Modelo', '') + ' ' +                 product_dict.get('Descripción', '')            ).lower()            for keyword in interest_keywords[familia_clean]:                if keyword in search_text:                    filtered_deals.append(product_dict)                    break    if not filtered_deals:        print(f"No se encontraron ofertas de interés en ninguna tienda.")        return    # Agrupar ofertas por modelo para el cálculo de margen    deals_by_model_for_margin = {}    for deal in filtered_deals:        model_key = (deal.get('Marca', 'N/A'), deal.get('Modelo', 'N/A'))        if model_key not in deals_by_model_for_margin:            deals_by_model_for_margin[model_key] = []        deals_by_model_for_margin[model_key].append(deal)    # Calcular el margen para cada oferta y seleccionar las mejores    final_deals_to_send = []    for model_key, deals_list in deals_by_model_for_margin.items():        # Ordenar por precio de venta de menor a mayor para identificar las ofertas        deals_list.sort(key=lambda p: clean_price_str(p.get('Precio Venta', '0')))                for i, current_deal in enumerate(deals_list):            current_price = clean_price_str(current_deal.get('Precio Venta', '0'))                        # Encontrar precios de unidades más caras del mismo modelo            higher_priced_units = [                clean_price_str(d.get('Precio Venta', '0'))                 for d in deals_list                 if clean_price_str(d.get('Precio Venta', '0')) > current_price            ]                        margen_calculado = 0.0            if higher_priced_units:                average_higher_price = sum(higher_priced_units) / len(higher_priced_units)                margen_calculado = average_higher_price - current_price                        current_deal['MargenCalculado'] = margen_calculado            final_deals_to_send.append(current_deal)    # Seleccionar los 3 mejores de cada modelo (ahora con margen calculado)    # Primero, agrupar por modelo nuevamente, pero ahora con el margen calculado    deals_by_model_for_top_selection = {}    for deal in final_deals_to_send:        model_key = (deal.get('Marca', 'N/A'), deal.get('Modelo', 'N/A'))        if model_key not in deals_by_model_for_top_selection:            deals_by_model_for_top_selection[model_key] = []        deals_by_model_for_top_selection[model_key].append(deal)    top_deals = []    for model_key, deals_list in deals_by_model_for_top_selection.items():        # Ordenar por margen (mayor a menor) y luego por precio (menor a mayor)        deals_list.sort(key=lambda p: (p['MargenCalculado'], -clean_price_str(p.get('Precio Venta', '0'))), reverse=True)        top_deals.extend(deals_list[:3])    if not top_deals:        print("No se encontraron ofertas válidas para enviar.")        return    # Ordenar la lista final por margen para enviar las mejores primero    top_deals.sort(key=lambda p: p['MargenCalculado'], reverse=True)    now = datetime.datetime.now()    end_of_day = now.replace(hour=END_SEND_HOUR, minute=0, second=0, microsecond=0)    if now.hour >= END_SEND_HOUR:        print("Fuera del horario de envío de mensajes.")        return    time_left_seconds = (end_of_day - now).total_seconds()    min_interval_seconds = 4 * 60    num_deals_to_send = len(top_deals)    ideal_interval = time_left_seconds / num_deals_to_send if num_deals_to_send > 0 else min_interval_seconds    send_interval = max(min_interval_seconds, ideal_interval)    print(f"Se encontraron {num_deals_to_send} ofertas de interés. Enviando cada {send_interval:.0f} segundos.")    for i, product in enumerate(top_deals):        print(f"Enviando oferta {i+1}/{num_deals_to_send}...")                # Usar el margen calculado        comparison_data = {            'reacondicionados': 'N/A', # Ya no es relevante            'nuevos': 'N/A', # Ya no es relevante            'margen': f"${product['MargenCalculado']:, .2f}"        }                message = format_slack_message(product, comparison_data)        send_slack_notification(message)                if i < num_deals_to_send - 1:            time.sleep(send_interval)    print(f"Envío de ofertas completado.")
    return top_deals

def send_deals_to_slack(top_deals):
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
        
        comparison_data = {
            'reacondicionados': 'N/A',
            'nuevos': 'N/A',
            'margen': f"${product['MargenCalculado']:,.2f}"
        }
        
        message = format_slack_message(product, comparison_data)
        send_slack_notification(message)
        
        if i < num_deals_to_send - 1:
            time.sleep(send_interval)

    print(f"Envío de ofertas completado.")