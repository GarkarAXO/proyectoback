import json
import time
import random
import re
import requests
from bs4 import BeautifulSoup
import csv

# ===== CONFIGURACIÓN =====
INPUT_FILE = "productos_agrupados_por_modelo.json"
OUTPUT_FILE = "modelos_nombre_comercial.json"
NO_ENCONTRADOS_FILE = "modelos_no_encontrados.csv"
LOTE_TAMANIO = 5   # Guardar cada 5 modelos
SCRAPERAPI_KEY = "aa9e791cec9d7c292e3066b886cc3f1e"
SCRAPERAPI_MAX_CONSULTAS = 1000
FUENTES_BUSQUEDA = [
    "site:amazon.com",
    "site:bestbuy.com",
    "site:mercadolibre.com.mx",
    "site:wikipedia.org"
]
# =========================

scraperapi_usadas = 325

def limpiar_modelo(modelo):
    modelo = re.sub(r"-MEM:.*", "", modelo, flags=re.IGNORECASE)
    modelo = re.sub(r"-RAM:.*", "", modelo, flags=re.IGNORECASE)
    modelo = modelo.strip()
    if modelo.upper().startswith("SM") and len(modelo) > 4 and "-" not in modelo:
        modelo = modelo[:2] + "-" + modelo[2:]
    return modelo

def buscar_en_google_normal(query):
    url = f"https://www.google.com/search?q={requests.utils.quote(query)}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            h3 = soup.find("h3")
            if h3:
                return h3.get_text().strip()
    except Exception as e:
        print(f"Error búsqueda normal: {e}")
    return None

def buscar_en_google_scraperapi(query):
    global scraperapi_usadas
    if scraperapi_usadas >= SCRAPERAPI_MAX_CONSULTAS:
        print("⚠️ Límite de ScraperAPI alcanzado, saltando...")
        return None
    
    scraperapi_usadas += 1
    google_url = f"https://www.google.com/search?q={requests.utils.quote(query)}"
    url = f"http://api.scraperapi.com?api_key={SCRAPERAPI_KEY}&url={google_url}"
    try:
        resp = requests.get(url, timeout=60)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            h3 = soup.find("h3")
            if h3:
                return h3.get_text().strip()
    except Exception as e:
        print(f"Error búsqueda ScraperAPI: {e}")
    return None

def buscar_nombre_comercial(marca, modelo):
    for fuente in FUENTES_BUSQUEDA:
        nombre = buscar_en_google_normal(f"{marca} {modelo} {fuente}")
        if nombre:
            return nombre
        nombre = buscar_en_google_scraperapi(f"{marca} {modelo} {fuente}")
        if nombre:
            return nombre
    return None

def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    modelos_unicos = set()
    for raw_modelo, productos in data.items():
        if not productos:
            continue
        producto = productos[0]
        marca = producto.get("Marca", "").strip()
        modelo = limpiar_modelo(producto.get("Modelo", "").strip())
        if marca and modelo:
            modelos_unicos.add((marca, modelo))

    modelos_unicos = list(modelos_unicos)
    print(f"Total de modelos únicos: {len(modelos_unicos)}")

    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            resultados = json.load(f)
    except FileNotFoundError:
        resultados = []

    procesados = {(r["Marca"], r["Modelo"]) for r in resultados}
    no_encontrados = []

    for i, (marca, modelo) in enumerate(modelos_unicos, start=1):
        if (marca, modelo) in procesados:
            continue

        nombre = buscar_nombre_comercial(marca, modelo)
        if nombre:
            resultados.append({"Marca": marca, "Modelo": modelo, "nombre_comercial": nombre})
            print(f"[OK] {marca} {modelo} → {nombre}")
        else:
            print(f"[NO] {marca} {modelo}")
            no_encontrados.append({"Marca": marca, "Modelo": modelo})

        time.sleep(random.uniform(1, 2))

        if i % LOTE_TAMANIO == 0:
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(resultados, f, indent=2, ensure_ascii=False)
            with open(NO_ENCONTRADOS_FILE, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=["Marca", "Modelo"])
                writer.writeheader()
                writer.writerows(no_encontrados)
            print(f"💾 Guardado parcial ({i}/{len(modelos_unicos)})")
            print(f"🔄 Consultas ScraperAPI usadas: {scraperapi_usadas}/{SCRAPERAPI_MAX_CONSULTAS}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False)
    with open(NO_ENCONTRADOS_FILE, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["Marca", "Modelo"])
        writer.writeheader()
        writer.writerows(no_encontrados)

    print(f"✅ Proceso completado. Archivo final en {OUTPUT_FILE}")
    print(f"📄 Modelos no encontrados guardados en {NO_ENCONTRADOS_FILE}")
    print(f"🔄 Total de consultas ScraperAPI usadas: {scraperapi_usadas}/{SCRAPERAPI_MAX_CONSULTAS}")

if __name__ == "__main__":
    main()
