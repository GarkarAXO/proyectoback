import json
import datetime
import os

from scraper_completo import scrape_store_for_families, agrupar_y_guardar_por_modelo

STORES_FILE = "stores.json"
OUTPUT_JSON = "productos_agrupados_por_modelo.json"
OUTPUT_FILTRADO = "productos_agrupados_filtrados.json"
MIN_HOURS_BETWEEN_SCRAPES = 6

def load_json_file(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Archivo {filename} no encontrado.")
        return None
    except json.JSONDecodeError as e:
        print(f"Error: Archivo {filename} no es un JSON válido. Detalles: {e}")
        return None

def limpiar_modelos_por_minimo_dispositivos(
    input_path=OUTPUT_JSON,
    output_path=OUTPUT_FILTRADO,
    minimo=5
):
    if not os.path.exists(input_path) or os.path.getsize(input_path) == 0:
        print(f"El archivo {input_path} no existe o está vacío. No se puede limpiar modelos.")
        return

    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"No se pudo abrir {input_path} para limpiar modelos: {e}")
        return

    filtrados = {
        modelo: dispositivos
        for modelo, dispositivos in data.items()
        if len(dispositivos) >= minimo
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(filtrados, f, indent=2, ensure_ascii=False)

    print(
        f"Modelos filtrados: {len(filtrados)} de {len(data)} modelos originales. "
        f"(mínimo {minimo} dispositivos por modelo)"
    )

def is_time_to_scrape(file_path, min_hours):
    """Verifica si han pasado al menos min_hours desde la última modificación del archivo."""
    if not os.path.exists(file_path):
        return True
    if os.path.getsize(file_path) == 0:
        return True
    last_modified = os.path.getmtime(file_path)
    last_dt = datetime.datetime.fromtimestamp(last_modified)
    now = datetime.datetime.now()
    elapsed_hours = (now - last_dt).total_seconds() / 3600.0
    if elapsed_hours >= min_hours:
        return True
    else:
        print(f"Último scraping fue hace {elapsed_hours:.2f} horas. No se hará scraping todavía.")
        return False

def main_orchestrator():
    print("Iniciando orquestador principal (scraping cada 6 horas si corresponde)...")

    stores_data = load_json_file(STORES_FILE)
    if stores_data is None:
        return

    familias = ["CELULARES"]  # Puedes cambiar familias aquí

    scraping_realizado = False

    if is_time_to_scrape(OUTPUT_JSON, MIN_HOURS_BETWEEN_SCRAPES):
        print("Ejecutando scraping ahora...\n")
        all_scraped_products = []
        for id_sucursal, nombre_sucursal in stores_data.items():
            print(f"Procesando tienda: {nombre_sucursal} (ID: {id_sucursal})")
            scraped_data_from_store = scrape_store_for_families(id_sucursal, nombre_sucursal, familias)
            all_scraped_products.extend(scraped_data_from_store)

        print(f"\n--- Scraping completado para todas las tiendas. Total de productos: {len(all_scraped_products)} ---")
        if all_scraped_products:
            agrupar_y_guardar_por_modelo(all_scraped_products, output_path=OUTPUT_JSON)
            scraping_realizado = True
        else:
            print(f"No se encontraron datos en ninguna tienda.")
    else:
        print("No se hará scraping en este ciclo. El archivo actual sigue vigente.")

    # Limpiar siempre, ya sea con datos nuevos o existentes
    limpiar_modelos_por_minimo_dispositivos(
        input_path=OUTPUT_JSON,
        output_path=OUTPUT_FILTRADO,
        minimo=5
    )
    print("Limpieza de modelos ejecutada.")

if __name__ == "__main__":
    main_orchestrator()
