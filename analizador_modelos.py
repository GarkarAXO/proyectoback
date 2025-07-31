import json
import numpy as np

INPUT = "productos_agrupados_filtrados.json"
OUTPUT = "analisis_modelos.json"
MARGEN_MINIMO = 500  # Solo guarda artículos con margen >= $500

def get_precio_float(producto):
    val = producto["Precio Promoción"]
    return float(str(val).replace("$", "").replace(",", "").strip())

def calcular_rango_dominante(precios):
    precios = np.array(precios)
    q1 = np.percentile(precios, 25)
    q3 = np.percentile(precios, 75)
    mediana = np.median(precios)
    rango_dominante = precios[(precios >= q1) & (precios <= q3)]
    if len(rango_dominante) == 0:
        return mediana, q1, q3  # fallback
    dominante_visual = np.mean(rango_dominante)
    return dominante_visual, q1, q3

def procesar_modelos(input_path=INPUT, output_path=OUTPUT):
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    resultados = {}

    for modelo, dispositivos in data.items():
        dispositivos_ordenados = sorted(dispositivos, key=get_precio_float)
        precios = [get_precio_float(p) for p in dispositivos_ordenados]
        if len(precios) < 5:
            continue

        dominante_visual, q1, q3 = calcular_rango_dominante(precios)

        # Buscar los dispositivos dentro del rango dominante
        dentro_dominante = [
            p for p in dispositivos_ordenados
            if get_precio_float(p) >= q1 and get_precio_float(p) <= q3
        ]
        if dentro_dominante:
            max_dom = max(dentro_dominante, key=get_precio_float)
            min_dom = min(dentro_dominante, key=get_precio_float)
            min_dom_precio = get_precio_float(min_dom)
        else:
            max_dom = min_dom = None
            min_dom_precio = q1  # fallback

        # Top 4 más baratos, con todos los márgenes y filtrado por margen mínimo
        top_4 = dispositivos_ordenados[:4]
        top_4_data = []
        for p in top_4:
            precio = get_precio_float(p)
            margen_vs_dominante_menor = round(min_dom_precio - precio, 2)
            if margen_vs_dominante_menor >= MARGEN_MINIMO:
                top_4_data.append({
                    "SKU": p["SKU"],
                    "Modelo": p["Modelo"],
                    "Precio Promoción": p["Precio Promoción"],
                    "Descripción": p["Descripción"],
                    "Sucursal": p.get("Sucursal", ""),
                    "MargenVsDominanteVisual": round(dominante_visual - precio, 2),
                    "MargenVsQ1": round(q1 - precio, 2),
                    "MargenVsDominanteMenor": margen_vs_dominante_menor
                })

        # Si después del filtro no hay top_4_data, omite este modelo
        if not top_4_data:
            continue

        resultados[modelo] = {
            "precio_dominante_visual": round(dominante_visual, 2),
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
        json.dump(resultados, f, indent=2, ensure_ascii=False)
    print(f"Análisis guardado en {output_path}")

if __name__ == "__main__":
    procesar_modelos()
