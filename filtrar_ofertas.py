
import csv
import glob
import os

def clean_price(price_str):
    """Convierte un string de precio como '$ 1,234.56' a un float."""
    try:
        # Quita el símbolo de moneda, las comas y los espacios
        cleaned_str = price_str.replace('$', '').replace(',', '').strip()
        return float(cleaned_str)
    except (ValueError, AttributeError):
        # Si el precio está vacío o mal formado, lo tratamos como infinito
        return float('inf')

def main():
    # Usamos glob para encontrar todos los archivos CSV generados anteriormente
    csv_files = glob.glob('*.csv')
    # Excluimos el posible archivo de salida de ejecuciones anteriores
    if 'mejores_ofertas.csv' in csv_files:
        csv_files.remove('mejores_ofertas.csv')

    best_deals = {}
    headers = []

    print(f"Procesando archivos: {csv_files}")

    for file_path in csv_files:
        try:
            with open(file_path, 'r', newline='', encoding='utf-8') as infile:
                reader = csv.DictReader(infile)
                if not headers:
                    headers = reader.fieldnames
                
                for row in reader:
                    marca = row.get('Marca', '').strip()
                    modelo = row.get('Modelo', '').strip()
                    
                    # Ignoramos filas sin marca o modelo
                    if not marca or not modelo:
                        continue

                    key = (marca, modelo)
                    current_price = clean_price(row.get('Precio Venta'))

                    # Si no hemos visto esta combinación, o si el precio actual es mejor,
                    # la guardamos.
                    if key not in best_deals or current_price < clean_price(best_deals[key].get('Precio Venta')):
                        best_deals[key] = row

        except FileNotFoundError:
            print(f"Advertencia: No se encontró el archivo {file_path}")
        except Exception as e:
            print(f"Ocurrió un error procesando {file_path}: {e}")

    if not best_deals:
        print("No se encontraron ofertas para procesar.")
        return

    # Escribimos los resultados en un nuevo archivo CSV
    output_filename = 'mejores_ofertas.csv'
    print(f"Escribiendo las mejores {len(best_deals)} ofertas en {output_filename}...")

    with open(output_filename, 'w', newline='', encoding='utf-8') as outfile:
        # Aseguramos que los headers sean los correctos
        writer = csv.DictWriter(outfile, fieldnames=headers)
        writer.writeheader()
        writer.writerows(best_deals.values())

    print("¡Proceso completado!")

if __name__ == "__main__":
    main()
