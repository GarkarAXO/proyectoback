import datetime
import time
import os
import json
import numpy as np
from collections import Counter, defaultdict
from dotenv import load_dotenv
from servicio_pse import clean_price_str
from notificador_slack import send_slack_notification, format_slack_message
from scraper_completo import obtener_imagenes_efectimundo

load_dotenv()

MIN_DOMINANT_FREQ = 3
MIN_PROFIT_THRESHOLD = 100.0
MIN_FINAL_PROFIT = 500
IMAGENES_CACHE_FILE = "imagenes_cache.json"

# Cargar configuración de orden
CONFIG_FILE = "config_orden_envio.json"
with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

FAMILIAS_ORDENADAS = config.get("familias_ordenadas", [])
SUCURSALES_ORDENADAS_RAW = config.get("sucursales_ordenadas", {})

if isinstance(SUCURSALES_ORDENADAS_RAW, dict):
    SUCURSALES_ORDENADAS = list(SUCURSALES_ORDENADAS_RAW.keys())
else:
    SUCURSALES_ORDENADAS = SUCURSALES_ORDENADAS_RAW

def detectar_ganga_stats(precios, precio_promocion):
    if len(precios) < 3:
        return {"mediana": 0, "q1": 0, "q3": 0, "zscore": 0}
    q1 = np.percentile(precios, 25)
    q3 = np.percentile(precios, 75)
    mediana = np.median(precios)
    desv = np.std(precios) if np.std(precios) != 0 else 1
    zscore = (precio_promocion - mediana) / desv
    return {"q1": q1, "q3": q3, "mediana": mediana, "zscore": zscore}

def estimate_intermediate_range(precios):
    q1 = np.percentile(precios, 25)
    q3 = np.percentile(precios, 75)
    return q1, q3

def process_and_send_all_deals(all_scraped_products):
    print(f"--- Procesando y enviando solo top 5 gangas (sin IA) de cada modelo ---")
    print(f"Total productos recibidos: {len(all_scraped_products)}")

    # Agrupar por modelo
    deals_by_model = {}
    for product in all_scraped_products:
        key = (product.get("Marca", "").strip(), product.get("Modelo", "").strip())
        deals_by_model.setdefault(key, []).append(product)

    final_deals_to_send = []

    for model_key, items in deals_by_model.items():
        items = [p for p in items if str(p.get('Tipo', '')).lower() != 'con_reporte']
        if len(items) < 2:
            continue

        precios_promocion = [clean_price_str(p.get("Precio Promoción", "0")) for p in items]
        conteo = Counter(precios_promocion)
        precio_dominante, frecuencia = conteo.most_common(1)[0]
        precio_maximo = max(precios_promocion)
        q1, q3 = estimate_intermediate_range(precios_promocion)

        for p in items:
            precio = clean_price_str(p.get("Precio Promoción", "0"))

            # 1. Descarta todo lo que esté entre el dominante y el máximo
            if precio_dominante <= precio <= precio_maximo:
                continue

            # 2. Solo considera precios menores al dominante
            if precio < precio_dominante:
                margen_dominante = precio_dominante - precio
                margen_maximo = precio_maximo - precio
                if margen_dominante >= MIN_PROFIT_THRESHOLD and margen_maximo >= MIN_FINAL_PROFIT:
                    stats = detectar_ganga_stats(precios_promocion, precio)
                    p["MargenDominante"] = margen_dominante
                    p["MargenMaximo"] = margen_maximo
                    p["precio_dominante"] = precio_dominante
                    p["precio_maximo"] = precio_maximo
                    p["rango_intermedio"] = f"{q1} - {q3}"
                    p["q1"] = q1
                    final_deals_to_send.append(p)
                    print(f"GANGA CANDIDATA: {p.get('Marca')} {p.get('Modelo')} ${p.get('Precio Promoción')}")

    print(f"Gangas candidatas totales encontradas: {len(final_deals_to_send)}")
    if not final_deals_to_send:
        print("No hay gangas candidatas que cumplan las condiciones.")
        return

    # Cargar caché si existe
    if os.path.exists(IMAGENES_CACHE_FILE):
        with open(IMAGENES_CACHE_FILE, "r") as f:
            imagenes_cache = json.load(f)
    else:
        imagenes_cache = {}

    # Agrupar gangas por modelo
    gangas_por_modelo = defaultdict(list)
    for ganga in final_deals_to_send:
        modelo_key = (ganga.get("Marca", "").strip(), ganga.get("Modelo", "").strip())
        gangas_por_modelo[modelo_key].append(ganga)

    # Tomar top 5 por modelo
    top5_por_modelo = []
    for modelo_key, gangas in gangas_por_modelo.items():
        gangas.sort(key=lambda x: clean_price_str(x.get("Precio Promoción", "0")))
        top_5_gangas = gangas[:5]  # Ahora tomamos 5 en lugar de 3
        if top_5_gangas:
            precio_mas_bajo = clean_price_str(top_5_gangas[0].get("Precio Promoción", "0"))
            top5_por_modelo.append((precio_mas_bajo, modelo_key, top_5_gangas))

    top5_por_modelo.sort(key=lambda x: x[0])

    # Aquí puedes integrar la lógica de envío a Slack si lo deseas
    print("Procesamiento terminado (sin IA en esta etapa).")
    print(f"Se han seleccionado {sum(len(x[2]) for x in top5_por_modelo)} dispositivos para enviar.")
