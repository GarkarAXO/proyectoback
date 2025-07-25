
import json
import datetime
import time
import os

# Importar funciones de los otros scripts
from scraper_completo import scrape_store_for_families
from procesador_ofertas import process_and_send_all_deals

# Archivos de configuración y estado
STORES_FILE = "stores.json"
# Horario de ejecución (en horas, formato 24h)
START_HOUR = 7  # 7 AM
END_HOUR = 20   # 8 PM

def load_json_file(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Archivo {filename} no encontrado.")
        return None
    except json.JSONDecodeError:
        print(f"Error: Archivo {filename} no es un JSON válido.")
        return None

def save_json_file(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def main_orchestrator():
    print("Iniciando orquestador principal...")

    # Cargar datos de sucursales
    stores_data = load_json_file(STORES_FILE)
    if stores_data is None:
        return

    # Definir las familias de productos a raspar
    familias = ["CONSOLAS DE JUEGOS", "JUEGOS DE VIDEO", "ACCESORIOS DE CONSOLAS", 
                "SMARTWATCH", "AUDIFONOS", "PROYECTORES", 
                "LAPTOP Y MINI LAPTOP", "PC ESCRITORIO", "MONITORES", "TABLETAS", "CELULARES"]

    while True:
        now = datetime.datetime.now()
        if START_HOUR <= now.hour < END_HOUR:
            print(f"Ejecutando proceso a las {now.strftime('%H:%M:%S')}")
            
            all_scraped_products = []
            for id_sucursal, nombre_sucursal in stores_data.items():
                print(f"Procesando tienda: {nombre_sucursal} (ID: {id_sucursal})")

                # Paso 1: Raspar datos de la tienda
                scraped_data_from_store = scrape_store_for_families(id_sucursal, nombre_sucursal, familias)
                all_scraped_products.extend(scraped_data_from_store)
            
            print(f"\n--- Scraping completado para todas las tiendas. Total de productos: {len(all_scraped_products)} ---")

            # Paso 2: Procesar y enviar ofertas a Slack
            if all_scraped_products:
                process_and_send_all_deals(all_scraped_products)
            else:
                print(f"No se encontraron datos en ninguna tienda. Saltando procesamiento de ofertas.")
            
            # Esperar hasta el siguiente ciclo de ejecución (por ejemplo, 1 hora)
            print(f"Proceso completado para hoy. Esperando 1 hora para el próximo ciclo.")
            time.sleep(3600) # Esperar 1 hora
            
        else:
            print(f"Fuera del horario de operación ({START_HOUR}:00 - {END_HOUR}:00). Esperando... {now.strftime('%H:%M:%S')}")
            # Esperar hasta la hora de inicio
            next_start_time = now.replace(hour=START_HOUR, minute=0, second=0, microsecond=0)
            if now.hour >= END_HOUR:
                next_start_time += datetime.timedelta(days=1)
            
            sleep_seconds = (next_start_time - now).total_seconds()
            if sleep_seconds < 0: # Should not happen if logic is correct, but for safety
                sleep_seconds = 60 # Wait 1 minute if somehow time is negative
            
            print(f"Esperando {int(sleep_seconds / 3600)} horas y {int((sleep_seconds % 3600) / 60)} minutos para el inicio de operaciones.")
            time.sleep(sleep_seconds)

if __name__ == "__main__":
    main_orchestrator()
