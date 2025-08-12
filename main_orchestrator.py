import json
import datetime
import os
import time
import logging
from full_scraper import scrape_store_by_categories, group_and_save_by_model
from model_analyzer import process_models
from slack_notifier import notify_detected_bargains

# Configuración básica de logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# --- Archivos de configuración y estado ---
CONFIG_FILE = "config_orden_envio.json"
SENT_STORES_FILE = "sent_branches.json"
STORES_FILE = "stores.json" # Fallback por si el config no existe

# --- Archivos de datos de salida ---
OUTPUT_JSON = "grouped_products_by_model.json"
OUTPUT_FILTRADO = "filtered_grouped_products.json"
ANALYSIS_JSON = "model_analysis.json"

# --- Constantes ---
STORES_PER_RUN = 3

def load_json_file(filename, default_value=None):
    """Carga un archivo JSON. Devuelve un valor por defecto si no se encuentra o hay un error."""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.warning(f"Archivo no encontrado: {filename}. Usando valor por defecto.")
        return default_value
    except json.JSONDecodeError as e:
        logging.error(f"Error decodificando JSON en {filename}: {e}")
        return default_value

def save_json_file(data, filename):
    """Guarda datos en un archivo JSON."""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_next_stores_to_process():
    """
    Determina las próximas N sucursales a procesar, rotando a través de toda la lista
    y persistiendo el estado entre días.
    """
    config = load_json_file(CONFIG_FILE)
    if not config or 'sucursales_ordenadas' not in config:
        logging.error("No se pudo cargar la configuración de sucursales o está mal formada.")
        return [], None

    ordered_stores = list(config['sucursales_ordenadas'].items())
    
    # Cargar sucursales ya procesadas, sin importar la fecha.
    sent_data = load_json_file(SENT_STORES_FILE, {'sucursales': []})
    sent_store_ids = sent_data.get('sucursales', [])

    pending_stores = [
        (store_id, store_name)
        for store_id, store_name in ordered_stores
        if store_id not in sent_store_ids
    ]

    # Si no hay pendientes, es hora de reiniciar el ciclo.
    if not pending_stores:
        logging.info("Todas las sucursales han sido procesadas. Reiniciando el ciclo.")
        sent_data['sucursales'] = []
        pending_stores = ordered_stores

    stores_to_process = pending_stores[:STORES_PER_RUN]
    
    # Actualizar la lista de enviados con las que se procesarán ahora.
    sent_data['sucursales'].extend([store_id for store_id, _ in stores_to_process])
    
    return stores_to_process, sent_data

def filter_models_by_min_devices(input_path=OUTPUT_JSON, output_path=OUTPUT_FILTRADO, minimo=5):
    data = load_json_file(input_path)
    if not data:
        logging.warning(f"El archivo {input_path} no existe o está vacío. No se puede filtrar.")
        return

    filtered = {
        model: items
        for model, items in data.items()
        if len(items) >= minimo
    }

    save_json_file(filtered, output_path)
    logging.info(
        f"Modelos filtrados: {len(filtered)} de {len(data)} modelos originales. "
        f"(mínimo {minimo} dispositivos por modelo)"
    )

def main_orchestrator():
    START_HOUR = 7
    END_HOUR = 22 

    while True:
        now = datetime.datetime.now()

        # --- Lógica de Horario ---
        if not (START_HOUR <= now.hour < END_HOUR):
            next_run = (now + datetime.timedelta(days=1)).replace(hour=START_HOUR, minute=0, second=0, microsecond=0)
            wait_seconds = (next_run - now).total_seconds()
            logging.info(f"⏸ Fuera de horario ({START_HOUR}:00-{END_HOUR}:00). Durmiendo por {wait_seconds/3600:.1f} horas.")
            time.sleep(wait_seconds)
            continue

        logging.info(f"⏱  Iniciando ciclo diario del orquestador - {now.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # --- Limpieza de Archivos Viejos ---
        if os.path.exists(OUTPUT_JSON):
            logging.info(f"Limpiando el archivo de resultados de la ejecución anterior: {OUTPUT_JSON}")
            os.remove(OUTPUT_JSON)
        
        # --- Selección de Sucursales ---
        stores_to_process, updated_sent_data = get_next_stores_to_process()
        save_json_file(updated_sent_data, SENT_STORES_FILE)
        logging.info(f"Sucursales a procesar hoy: {[name for _, name in stores_to_process]}")

        # --- Scraping ---
        categories = load_json_file(CONFIG_FILE, {}).get('familias_ordenadas', [])
        if not categories:
            logging.error("No se encontraron categorías. Usando lista de fallback.")
            categories = ["CELULARES", "CONSOLAS DE JUEGOS", "AUDIFONOS", "SMARTWATCH", "TABLETAS"]

        logging.info("🔍 Ejecutando scraping...")
        all_scraped_products = []
        for store_id, store_name in stores_to_process:
            logging.debug(f"📍 Procesando tienda: {store_name} (ID: {store_id})")
            scraped_data = scrape_store_by_categories(store_id, store_name, categories)
            all_scraped_products.extend(scraped_data)

        logging.info(f"--- ✅ Scraping completado. Total de productos: {len(all_scraped_products)} ---")
        if all_scraped_products:
            group_and_save_by_model(all_scraped_products, output_path=OUTPUT_JSON)
        else:
            logging.warning("⚠ No se encontraron productos en este ciclo de scraping.")

        # --- Análisis y Notificación ---
        filter_models_by_min_devices(input_path=OUTPUT_JSON, output_path=OUTPUT_FILTRADO, minimo=5)
        process_models(input_path=OUTPUT_FILTRADO, output_path=ANALYSIS_JSON)
        notify_detected_bargains(ANALYSIS_JSON)

        # --- Pausa hasta el día siguiente ---
        logging.info("✅ Ciclo diario finalizado.")
        next_run = (now + datetime.timedelta(days=1)).replace(hour=START_HOUR, minute=0, second=0, microsecond=0)
        wait_seconds = (next_run - now).total_seconds()
        logging.info(f"Durmiendo hasta mañana a las {START_HOUR}:00 (aprox. {wait_seconds / 3600:.1f} horas).")
        time.sleep(wait_seconds)

if __name__ == "__main__":
    main_orchestrator()