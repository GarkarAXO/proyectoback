import datetime
import time
import os
import json
import numpy as np
from collections import Counter, defaultdict
from dotenv import load_dotenv
from servicio_pse import clean_price_str
from notificador_slack import send_slack_notification, format_slack_message
from openai import OpenAI
from scraper_completo import obtener_imagenes_efectimundo

load_dotenv()
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

START_SEND_HOUR = 7
END_SEND_HOUR = 20
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

# Convertir a lista de claves ordenadas si es un dict
if isinstance(SUCURSALES_ORDENADAS_RAW, dict):
    SUCURSALES_ORDENADAS = list(SUCURSALES_ORDENADAS_RAW.keys())
else:
    SUCURSALES_ORDENADAS = SUCURSALES_ORDENADAS_RAW

def analyze_offer_with_openai(product_data, comparison_data, productos_modelo=None):
    # productos_modelo es una lista con los otros precios/promos de ese modelo para contexto
    precios = [float(p.get("Precio Promoción", "0").replace("$", "").replace(",", "")) for p in productos_modelo or [] if p.get("Precio Promoción")]
    precios_str = ", ".join(f"${int(p)}" for p in sorted(precios))
    margen = comparison_data.get("MargenVsDominanteMenor") or 0

    prompt = f"""
Analiza la siguiente oportunidad para reventa considerando los siguientes datos del producto y el contexto de precios similares.
¿Es una verdadera ganga para revender? Responde SOLO 'Sí' o 'No' en la primera línea. En la segunda, una breve razón (máx 20 palabras).

- Precio del producto: {product_data['Precio Promoción']}
- Margen estimado vs dominante menor: ${margen:,.0f}
- Marca: {product_data['Marca']}
- Modelo: {product_data['Modelo']}
- Descripción: {product_data['Descripción']}
- Sucursal: {product_data['Sucursal']}
- Rango de precios de este modelo: {precios_str}
- Top 4 más baratos: {precios_str[:4]}
"""

    try:
        if not openai.api_key:
            raise ValueError("OPENAI_API_KEY no configurada.")

        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un experto analista de oportunidades de compra-venta y reventa en el sector electrónico."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=60,
            temperature=0.2
        )
        return response.choices[0].message.content.strip()
    except ValueError as ve:
        print(f"Advertencia: {ve}. No se realizará el análisis de IA.")
        return "Análisis de IA no disponible (API Key no configurada)"
    except Exception as e:
        print(f"Error al llamar a OpenAI: {e}")
        return "Análisis de IA no disponible (Error de IA)"

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
    print(f"--- Procesando y enviando solo top 3 gangas validadas por IA de cada modelo (flujo rápido) ---")
    print(f"Total productos recibidos: {len(all_scraped_products)}")

    # Agrupar por modelo
    deals_by_model = {}
    for product in all_scraped_products:
        key = (product.get("Marca", "").strip(), product.get("Modelo", "").strip())
        deals_by_model.setdefault(key, []).append(product)

    final_deals_to_send = []

    for model_key, items in deals_by_model.items():
        # Filtrar productos dañados por campo tipo
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

            # 2. Solo considera para IA los precios menores al dominante
            if precio < precio_dominante:
                margen_dominante = precio_dominante - precio
                margen_maximo = precio_maximo - precio
                if margen_dominante >= MIN_PROFIT_THRESHOLD and margen_maximo >= MIN_FINAL_PROFIT:
                    stats = detectar_ganga_stats(precios_promocion, precio)
                    ia_result = analyze_offer_with_openai(p, stats, precios_promocion)
                    if ia_result.strip().lower().startswith("sí") or ia_result.strip().lower().startswith("si"):
                        p["MargenDominante"] = margen_dominante
                        p["MargenMaximo"] = margen_maximo
                        p["precio_dominante"] = precio_dominante
                        p["precio_maximo"] = precio_maximo
                        p["rango_intermedio"] = f"{q1} - {q3}"
                        p["q1"] = q1
                        p["openai_ganga"] = ia_result
                        final_deals_to_send.append(p)
                        print(f"GANGA VALIDADA y añadida: {p.get('Marca')} {p.get('Modelo')} ${p.get('Precio Promoción')}")
                    else:
                        print(f"GANGA RECHAZADA por IA: {p.get('Marca')} {p.get('Modelo')} ${p.get('Precio Promoción')} | {ia_result}")

    print(f"Gangas validadas totales encontradas: {len(final_deals_to_send)}")
    if not final_deals_to_send:
        print("No hay gangas validadas por IA que cumplan las condiciones.")
        return

    now = datetime.datetime.now()
    if now.hour >= END_SEND_HOUR:
        print("Fuera del horario permitido.")
        return

    intervalo_envio = 180  # 3 minutos fijos entre envíos

    # Cargar caché si existe
    if os.path.exists(IMAGENES_CACHE_FILE):
        with open(IMAGENES_CACHE_FILE, "r") as f:
            imagenes_cache = json.load(f)
    else:
        imagenes_cache = {}

    # --- Agrupar por modelo y obtener top 3 más baratos ---
    gangas_por_modelo = defaultdict(list)
    for ganga in final_deals_to_send:
        modelo_key = (ganga.get("Marca", "").strip(), ganga.get("Modelo", "").strip())
        gangas_por_modelo[modelo_key].append(ganga)

    top3_por_modelo = []
    for modelo_key, gangas in gangas_por_modelo.items():
        gangas.sort(key=lambda x: clean_price_str(x.get("Precio Promoción", "0")))
        top_3_gangas = gangas[:3]
        if top_3_gangas:
            precio_mas_bajo = clean_price_str(top_3_gangas[0].get("Precio Promoción", "0"))
            top3_por_modelo.append((precio_mas_bajo, modelo_key, top_3_gangas))

    # Ordenar modelos por el precio más bajo de su top 3 (de menor a mayor)
    top3_por_modelo.sort(key=lambda x: x[0])

    # Enviar a Slack primero los modelos más baratos
    for _, modelo_key, gangas in top3_por_modelo:
        print(f"\nModelo: {modelo_key} | Top 3 gangas para enviar:")
        for i, producto in enumerate(gangas):
            print(f"  {i+1}. {producto.get('Marca')} {producto.get('Modelo')} ${producto.get('Precio Promoción')}")
            product_id = producto.get("Prenda / Sku Lote", "N/A")
            if product_id in imagenes_cache:
                producto["Imagenes"] = imagenes_cache[product_id]
            else:
                imagenes = obtener_imagenes_efectimundo(product_id)
                imagenes_cache[product_id] = imagenes
                producto["Imagenes"] = imagenes

            comparison_data = {
                "precio_dominante": producto["precio_dominante"],
                "precio_maximo": producto["precio_maximo"],
                "rango_intermedio": producto.get("rango_intercuartilico", producto.get("rango_intermedio", "")),
                "margen": f"${producto['MargenDominante']:,.2f}",
                "margen_con_mayor": f"${producto['MargenMaximo']:,.2f}",
                "rango_descartado": f"${producto['precio_dominante']:,.0f}–${producto['precio_maximo']:,.0f}",
                "product_id": product_id,
                "openai_ganga": producto["openai_ganga"]
            }


            payload = format_slack_message(producto, comparison_data)
            send_slack_notification(payload)

            if i < len(gangas) - 1:
                time.sleep(intervalo_envio)

    with open(IMAGENES_CACHE_FILE, "w") as f:
        json.dump(imagenes_cache, f, indent=2)

    print("Proceso completado.")
