import json
import datetime
import os
import time
import logging
from slack_notifier import notify_detected_bargains, load_state

# Configuración básica de logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("http.client").setLevel(logging.WARNING)

STORES_FILE = "stores.json"
OUTPUT_JSON = "grouped_products_by_model.json"
OUTPUT_FILTRADO = "filtered_grouped_products.json"
ANALYSIS_JSON = "model_analysis.json"

def load_json_file(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as e:
        logging.error(f"Archivo {filename} no es un JSON válido. Detalles: {e}")
        return None

def filter_models_by_min_devices(input_path=OUTPUT_JSON, output_path=OUTPUT_FILTRADO, minimo=5):
    if not os.path.exists(input_path) or os.path.getsize(input_path) == 0:
        logging.warning(f"El archivo {input_path} no existe o está vacío. No se puede limpiar modelos.")
        return

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    filtered = {
        model: items
        for model, items in data.items()
        if len(items) >= minimo
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(filtered, f, indent=2, ensure_ascii=False)

    logging.info(
        f"Modelos filtrados: {len(filtered)} de {len(data)} modelos originales. "
        f"(mínimo {minimo} dispositivos por modelo)"
    )

def main_orchestrator():
    START_HOUR = 7
    END_HOUR = 19  # 7 am a 7:59 pm

    while True:
        now = datetime.datetime.now()
        today_str = str(now.date())

        # Handle sleeping outside of allowed hours
        if now.hour < START_HOUR or now.hour >= END_HOUR:
            if now.hour >= END_HOUR:
                next_run = now.replace(hour=START_HOUR, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
            else:
                next_run = now.replace(hour=START_HOUR, minute=0, second=0, microsecond=0)

            wait_seconds = (next_run - now).total_seconds()
            logging.info(f"⏸ Fuera del horario permitido ({START_HOUR}:00 a {END_HOUR}:00). Hora actual: {now.strftime('%H:%M')}.")
            logging.info(f"   Durmiendo hasta las {START_HOUR}:00... ({wait_seconds//60:.0f} minutos)")
            time.sleep(wait_seconds)
            continue

        # Load state to check if notification cycle is complete for today
        state = load_state()
        if state.get("notification_completed_today", False) and state.get("last_notification_date") == today_str:
            logging.info(f"✅ Notificaciones para hoy ({today_str}) ya enviadas. Durmiendo hasta mañana.")
            next_run = now.replace(hour=START_HOUR, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
            wait_seconds = (next_run - now).total_seconds()
            time.sleep(wait_seconds)
            continue

        logging.info(f"⏱ Iniciando orquestador principal - {now.strftime('%Y-%m-%d %H:%M:%S')}")
        stores_data = load_json_file(STORES_FILE)
        if stores_data is None:
            logging.warning("⚠ No se pudo cargar el archivo de tiendas.")
            time.sleep(60 * 30)
            continue

        categories = [
            "CELULARES",
            "CONSOLAS DE JUEGOS",
            "AUDIFONOS",
            "SMARTWATCH",
            "TABLETAS",
            "LAPTOP Y MINI LAPTOP",
            "PC ESCRITORIO",
            "MONITORES",
            "PROYECTORES",
            "JUEGOS DE VIDEO",
            "ACCESORIOS DE CONSOLAS"
        ]

        logging.info("🔍 Ejecutando scraping ahora...")
        all_scraped_products = []
        for store_id, store_name in stores_data.items():
            logging.debug(f"📍 Procesando tienda: {store_name} (ID: {store_id})")
            scraped_data = scrape_store_by_categories(store_id, store_name, categories)
            all_scraped_products.extend(scraped_data)

        logging.info(f"--- ✅ Scraping completado. Total de productos: {len(all_scraped_products)} ---")
        if all_scraped_products:
            group_and_save_by_model(all_scraped_products, output_path=OUTPUT_JSON)
        else:
            logging.warning("⚠ No se encontraron datos en ninguna tienda.")

        filter_models_by_min_devices(input_path=OUTPUT_JSON, output_path=OUTPUT_FILTRADO, minimo=5)
        process_models(input_path=OUTPUT_FILTRADO, output_path=ANALYSIS_JSON)
        notify_detected_bargains(ANALYSIS_JSON)

        logging.info("✅ Ciclo finalizado. Durmiendo hasta el inicio del próximo ciclo de notificaciones.")
        next_run = now.replace(hour=START_HOUR, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
        wait_seconds = (next_run - now).total_seconds()
        time.sleep(wait_seconds)

if __name__ == "__main__":
    main_orchestrator()
