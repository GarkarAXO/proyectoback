import datetime
import time
import os
import json
import numpy as np
from collections import Counter, defaultdict
from dotenv import load_dotenv
from pse_service import clean_price_str
from slack_notifier import send_slack_notification, format_slack_message
from full_scraper import get_images_by_sku

load_dotenv()

MIN_DOMINANT_FREQ = 3
MIN_PROFIT_THRESHOLD = 100.0
MIN_FINAL_PROFIT = 500
IMAGES_CACHE_FILE = "image_cache.json"
CONFIG_FILE = "config_send_order.json"

with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

SORTED_FAMILIES = config.get("familias_ordenadas", [])
SORTED_BRANCHES_RAW = config.get("sucursales_ordenadas", {})

if isinstance(SORTED_BRANCHES_RAW, dict):
    SORTED_BRANCHES = list(SORTED_BRANCHES_RAW.keys())
else:
    SORTED_BRANCHES = SORTED_BRANCHES_RAW

def detect_bargain_stats(prices, target_price):
    if len(prices) < 3:
        return {"median": 0, "q1": 0, "q3": 0, "zscore": 0}
    q1 = np.percentile(prices, 25)
    q3 = np.percentile(prices, 75)
    median = np.median(prices)
    std_dev = np.std(prices) if np.std(prices) != 0 else 1
    zscore = (target_price - median) / std_dev
    return {"q1": q1, "q3": q3, "median": median, "zscore": zscore}

def estimate_intermediate_range(prices):
    q1 = np.percentile(prices, 25)
    q3 = np.percentile(prices, 75)
    return q1, q3

def process_and_send_all_deals(all_scraped_products):
    print(f"--- Procesando y enviando solo top 5 gangas (sin IA) de cada modelo ---")
    print(f"Total productos recibidos: {len(all_scraped_products)}")

    deals_by_model = defaultdict(list)
    for product in all_scraped_products:
        key = (product.get("Marca", "").strip(), product.get("Modelo", "").strip())
        deals_by_model[key].append(product)

    final_deals_to_send = []

    for model_key, items in deals_by_model.items():
        items = [p for p in items if str(p.get('Tipo', '')).lower() != 'con_reporte']
        if len(items) < 2:
            continue

        promo_prices = [clean_price_str(p.get("Precio Promoción", "0")) for p in items]
        count = Counter(promo_prices)
        dominant_price, freq = count.most_common(1)[0]
        max_price = max(promo_prices)
        q1, q3 = estimate_intermediate_range(promo_prices)

        for p in items:
            price = clean_price_str(p.get("Precio Promoción", "0"))
            if dominant_price <= price <= max_price:
                continue
            if price < dominant_price:
                margin_dominant = dominant_price - price
                margin_max = max_price - price
                if margin_dominant >= MIN_PROFIT_THRESHOLD and margin_max >= MIN_FINAL_PROFIT:
                    stats = detect_bargain_stats(promo_prices, price)
                    p["MargenDominante"] = margin_dominant
                    p["MargenMaximo"] = margin_max
                    p["precio_dominante"] = dominant_price
                    p["precio_maximo"] = max_price
                    p["rango_intermedio"] = f"{q1} - {q3}"
                    p["q1"] = q1
                    final_deals_to_send.append(p)
                    print(f"GANGA CANDIDATA: {p.get('Marca')} {p.get('Modelo')} ${p.get('Precio Promoción')}")

    print(f"Gangas candidatas totales encontradas: {len(final_deals_to_send)}")
    if not final_deals_to_send:
        print("No hay gangas candidatas que cumplan las condiciones.")
        return

    if os.path.exists(IMAGES_CACHE_FILE):
        with open(IMAGES_CACHE_FILE, "r") as f:
            image_cache = json.load(f)
    else:
        image_cache = {}

    grouped_deals = defaultdict(list)
    for deal in final_deals_to_send:
        model_key = (deal.get("Marca", "").strip(), deal.get("Modelo", "").strip())
        grouped_deals[model_key].append(deal)

    top5_by_model = []
    for model_key, deals in grouped_deals.items():
        deals.sort(key=lambda x: clean_price_str(x.get("Precio Promoción", "0")))
        top_5_deals = deals[:5]
        if top_5_deals:
            lowest_price = clean_price_str(top_5_deals[0].get("Precio Promoción", "0"))
            top5_by_model.append((lowest_price, model_key, top_5_deals))

    top5_by_model.sort(key=lambda x: x[0])

    print("Procesamiento terminado (sin IA en esta etapa).")
    print(f"Se han seleccionado {sum(len(x[2]) for x in top5_by_model)} dispositivos para enviar.")
