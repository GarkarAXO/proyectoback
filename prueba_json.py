import json

with open("analisis_modelos.json", "r", encoding="utf-8") as f:
    analisis = json.load(f)

for modelo_key, info in analisis.items():
    print("Modelo:", modelo_key)
    print("Top 4 más baratos:", info.get("top_4_mas_baratos"))
    if info.get("top_4_mas_baratos"):
        primer_art = info["top_4_mas_baratos"][0]
        precio_min_str = primer_art.get("Precio Promoción", "").replace("$", "").replace(",", "").strip()
        try:
            precio_min = float(precio_min_str)
        except Exception:
            precio_min = 0
        q1 = info.get("q1", 0)
        etiqueta_rango_bajo = f"${precio_min:,.0f} a ${q1:,.0f}"
        print("Etiqueta rango bajo:", etiqueta_rango_bajo)
    print("---")
    break  # Solo probar el primer modelo para ver la salida
