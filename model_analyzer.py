import json
import numpy as np

INPUT_FILE = "filtered_grouped_products.json"
OUTPUT_FILE = "model_analysis.json"
MIN_MARGIN = 500  # Solo guarda artículos con margen >= $500

def get_price_float(product):
    val = product["Precio Promoción"]
    return float(str(val).replace("$", "").replace(",", "").strip())

def calculate_dominant_range(prices):
    prices = np.array(prices)
    q1 = np.percentile(prices, 25)
    q3 = np.percentile(prices, 75)
    median = np.median(prices)
    dominant_range = prices[(prices >= q1) & (prices <= q3)]
    if len(dominant_range) == 0:
        return median, q1, q3
    dominant_avg = np.mean(dominant_range)
    return dominant_avg, q1, q3

def process_models(input_path=INPUT_FILE, output_path=OUTPUT_FILE):
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    results = {}

    for model, devices in data.items():
        sorted_devices = sorted(devices, key=get_price_float)
        prices = [get_price_float(p) for p in sorted_devices]
        if len(prices) < 5:
            continue

        dominant_avg, q1, q3 = calculate_dominant_range(prices)

        in_dominant = [
            p for p in sorted_devices
            if q1 <= get_price_float(p) <= q3
        ]
        if in_dominant:
            max_dom = max(in_dominant, key=get_price_float)
            min_dom = min(in_dominant, key=get_price_float)
            min_dom_price = get_price_float(min_dom)
        else:
            max_dom = min_dom = None
            min_dom_price = q1

        top_4 = sorted_devices[:4]
        top_4_data = []
        for p in top_4:
            price = get_price_float(p)
            margin_vs_min_dom = round(min_dom_price - price, 2)
            if margin_vs_min_dom >= MIN_MARGIN:
                top_4_data.append({
                    "SKU": p["SKU"],
                    "Modelo": p["Modelo"],
                    "Precio Promoción": p["Precio Promoción"],
                    "Descripción": p["Descripción"],
                    "Sucursal": p.get("Sucursal", ""),
                    "MargenVsDominanteVisual": round(dominant_avg - price, 2),
                    "MargenVsQ1": round(q1 - price, 2),
                    "MargenVsDominanteMenor": margin_vs_min_dom
                })

        if not top_4_data:
            continue

        results[model] = {
            "precio_dominante_visual": round(dominant_avg, 2),
            "q1": round(q1, 2),
            "q3": round(q3, 2),
            "articulo_dominante_mayor": {
                "SKU": max_dom["SKU"],
                "Modelo": max_dom["Modelo"],
                "Precio Promoción": max_dom["Precio Promoción"],
                "Descripción": max_dom["Descripción"],
                "Sucursal": max_dom.get("Sucursal", "")
            } if max_dom else {},
            "articulo_dominante_menor": {
                "SKU": min_dom["SKU"],
                "Modelo": min_dom["Modelo"],
                "Precio Promoción": min_dom["Precio Promoción"],
                "Descripción": min_dom["Descripción"],
                "Sucursal": min_dom.get("Sucursal", "")
            } if min_dom else {},
            "top_4_mas_baratos": top_4_data
        }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"Análisis guardado en {output_path}")

if __name__ == "__main__":
    process_models()
