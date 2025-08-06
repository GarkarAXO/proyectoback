import json
import datetime
import os
import time
from scraper_completo import scrape_store_for_families, agrupar_y_guardar_por_modelo
from analizador_modelos import procesar_modelos
from notificador_slack import notificar_gangas_encontradas

STORES_FILE = "stores.json"
OUTPUT_JSON = "productos_agrupados_por_modelo.json"
OUTPUT_FILTRADO = "productos_agrupados_filtrados.json"
ANALISIS_JSON = "analisis_modelos.json"
MIN_HOURS_BETWEEN_SCRAPES = 6  # horas

def load_json_file(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
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

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

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
    START_HOUR = 7
    END_HOUR = 19  # 7 am a 7:59 pm

    while True:
        now = datetime.datetime.now()

        if now.hour < START_HOUR or now.hour >= END_HOUR:
            if now.hour >= END_HOUR:
                next_run = now.replace(hour=START_HOUR, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
            else:
                next_run = now.replace(hour=START_HOUR, minute=0, second=0, microsecond=0)

            wait_seconds = (next_run - now).total_seconds()
            print(f"⏸ Fuera del horario permitido ({START_HOUR}:00 a {END_HOUR}:00). Hora actual: {now.strftime('%H:%M')}.")
            print(f"   Durmiendo hasta las {START_HOUR}:00... ({wait_seconds//60:.0f} minutos)")
            time.sleep(wait_seconds)
            continue

        print(f"\n⏱ Iniciando orquestador principal - {now.strftime('%Y-%m-%d %H:%M:%S')}")
        stores_data = load_json_file(STORES_FILE)
        if stores_data is None:
            print("⚠ No se pudo cargar el archivo de tiendas.")
            time.sleep(60 * 30)
            continue

        familias = [
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

        if is_time_to_scrape(OUTPUT_JSON, MIN_HOURS_BETWEEN_SCRAPES):
            print("🔍 Ejecutando scraping ahora...\n")
            all_scraped_products = []
            for id_sucursal, nombre_sucursal in stores_data.items():
                print(f"📍 Procesando tienda: {nombre_sucursal} (ID: {id_sucursal})")
                scraped_data_from_store = scrape_store_for_families(id_sucursal, nombre_sucursal, familias)
                all_scraped_products.extend(scraped_data_from_store)

            print(f"\n--- ✅ Scraping completado. Total de productos: {len(all_scraped_products)} ---")
            if all_scraped_products:
                agrupar_y_guardar_por_modelo(all_scraped_products, output_path=OUTPUT_JSON)
            else:
                print("⚠ No se encontraron datos en ninguna tienda.")
        else:
            print("⏭ No se hará scraping en este ciclo. El archivo actual sigue vigente.")

        limpiar_modelos_por_minimo_dispositivos(input_path=OUTPUT_JSON, output_path=OUTPUT_FILTRADO, minimo=5)
        procesar_modelos(input_path=OUTPUT_FILTRADO, output_path=ANALISIS_JSON)
        notificar_gangas_encontradas(ANALISIS_JSON)

        print("\n✅ Ciclo finalizado. Esperando 6 horas antes del siguiente...")
        time.sleep(60 * 60 * 6)

if __name__ == "__main__":
    main_orchestrator()
