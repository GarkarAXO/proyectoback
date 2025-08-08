import json
import datetime
import os

from full_scraper import scrape_store_by_categories, group_and_save_by_model

STORES_FILE = "stores.json"
GROUPED_JSON = "grouped_products_by_model.json"
FILTERED_JSON = "filtered_grouped_products.json"
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

def filter_models_by_min_devices(
    input_path=GROUPED_JSON,
    output_path=FILTERED_JSON,
    minimum=8
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

    filtered = {
        model: devices
        for model, devices in data.items()
        if len(devices) >= minimum
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(filtered, f, indent=2, ensure_ascii=False)

    print(
        f"Modelos filtrados: {len(filtered)} de {len(data)} modelos originales. "
        f"(mínimo {minimum} dispositivos por modelo)"
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

def run_orchestrator():
    print("Iniciando orquestador principal (scraping cada 6 horas si corresponde)...")

    stores_data = load_json_file(STORES_FILE)
    if stores_data is None:
        return

    categories = ["CELULARES"]  # Puedes cambiar categorías aquí

    did_scrape = False

    if is_time_to_scrape(GROUPED_JSON, MIN_HOURS_BETWEEN_SCRAPES):
        print("Ejecutando scraping ahora...\n")
        all_scraped_products = []
        for store_id, store_name in stores_data.items():
            print(f"Procesando tienda: {store_name} (ID: {store_id})")
            store_products = scrape_store_by_categories(store_id, store_name, categories)
            all_scraped_products.extend(store_products)

        print(f"\n--- Scraping completado para todas las tiendas. Total de productos: {len(all_scraped_products)} ---")
        if all_scraped_products:
            group_and_save_by_model(all_scraped_products, output_path=GROUPED_JSON)
            did_scrape = True
        else:
            print("No se encontraron datos en ninguna tienda.")
    else:
        print("No se hará scraping en este ciclo. El archivo actual sigue vigente.")

    # Limpiar siempre, con o sin scraping nuevo
    filter_models_by_min_devices(
        input_path=GROUPED_JSON,
        output_path=FILTERED_JSON,
        minimum=8
    )
    print("Limpieza de modelos ejecutada.")

if __name__ == "__main__":
    run_orchestrator()
