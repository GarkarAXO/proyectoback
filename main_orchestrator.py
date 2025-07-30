import json
import datetime
import time
import os

from scraper_completo import scrape_store_for_families, agrupar_y_guardar_por_modelo

# Archivos de configuración y estado
STORES_FILE = "stores.json"
START_HOUR = 7  # 7 AM
END_HOUR = 20   # 8 PM

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

def main_orchestrator():
    print("Iniciando orquestador principal (solo scraping y guardado)...")

    stores_data = load_json_file(STORES_FILE)
    if stores_data is None:
        return

    familias = ["CELULARES"]  # Puedes cambiar familias aquí

    # --- SOLO UNA EJECUCIÓN, SIN BUCLE INFINITO ---
    now = datetime.datetime.now()
    if START_HOUR <= now.hour < END_HOUR:
        print(f"Ejecutando scraping a las {now.strftime('%H:%M:%S')}")
        
        all_scraped_products = []
        for id_sucursal, nombre_sucursal in stores_data.items():
            print(f"Procesando tienda: {nombre_sucursal} (ID: {id_sucursal})")
            scraped_data_from_store = scrape_store_for_families(id_sucursal, nombre_sucursal, familias)
            all_scraped_products.extend(scraped_data_from_store)
        
        print(f"\n--- Scraping completado para todas las tiendas. Total de productos: {len(all_scraped_products)} ---")

        # Guardar agrupado por modelo
        if all_scraped_products:
            agrupar_y_guardar_por_modelo(all_scraped_products)
        else:
            print(f"No se encontraron datos en ninguna tienda.")
        
    else:
        print(f"Fuera del horario de operación ({START_HOUR}:00 - {END_HOUR}:00). Son las {now.strftime('%H:%M:%S')}. No se ejecutará scraping.")

if __name__ == "__main__":
    main_orchestrator()
