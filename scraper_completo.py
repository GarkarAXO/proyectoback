import json
import csv
import urllib.request
import urllib.parse
from html.parser import HTMLParser
import os

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_th = False
        self.in_tr = False
        self.in_td = False
        self.headers = []
        self.rows = []
        self.current_row = []

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.in_table = True
        elif tag == 'th':
            self.in_th = True
        elif tag == 'tr':
            self.in_tr = True
            self.current_row = []
        elif tag == 'td':
            self.in_td = True

    def handle_endtag(self, tag):
        if tag == 'table':
            self.in_table = False
        elif tag == 'th':
            self.in_th = False
        elif tag == 'tr':
            self.in_tr = False
            if self.current_row:
                self.rows.append(self.current_row)
        elif tag == 'td':
            self.in_td = False

    def handle_data(self, data):
        if self.in_th:
            self.headers.append(data.strip())
        elif self.in_td:
            self.current_row.append(data.strip())

def fetch_page_data(page_number, familia, id_sucursal):
    familia_encoded = urllib.parse.quote(familia)
    url = f'https://efectimundo.com.mx/catalogo/consulta_catalogo.php?metodo=consulta_catalogo&salida=res&id_sucursal={id_sucursal}&ramo=&familia={familia_encoded}&tipo=&prenda=&marca=&modelo=&descripcion=&col_order='
    headers = {
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'es-419,es;q=0.6',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Origin': 'https://efectimundo.com.mx',
        'Pragma': 'no-cache',
        'Referer': 'https://efectimundo.com.mx/catalogo/catalogo.php',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-GPC': '1',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
        'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Brave";v="138"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"'
    }
    data = urllib.parse.urlencode({'pagina': page_number}).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            response_content = response.read().decode('utf-8')
            parsed_json = json.loads(response_content)
            return parsed_json
    except urllib.error.URLError as e:
        print(f"DEBUG: Error de URL para {familia} en sucursal {id_sucursal}, página {page_number}: {e}", flush=True)
        return None
    except json.JSONDecodeError as e:
        print(f"DEBUG: Error de JSON para {familia} en sucursal {id_sucursal}, página {page_number}: {e}", flush=True)
        # print(f"DEBUG: Contenido que causó el error JSON (primeros 500 chars): {response_content[:500]}...", flush=True)
        return None

def scrape_store_for_families(id_sucursal, nombre_sucursal, familias):
    all_products_from_store = []
    for familia in familias:
        all_rows = []
        headers = []

        print(f"\n--- Procesando Familia: {familia} en {nombre_sucursal} ({id_sucursal}) ---")

        try:
            initial_data = fetch_page_data(1, familia, id_sucursal)
            
            if not initial_data or not initial_data.get('tabla'):
                print(f"    DEBUG: No se encontraron datos o tabla para {familia} en {nombre_sucursal}. Saltando.")
                continue

            total_pages = int(initial_data.get('pag_final', 1))
            total_registros_esperados = int(initial_data.get('rowCount', 0))
            page_size = 50
            total_pages_calculadas = (total_registros_esperados + page_size - 1) // page_size
            
            print(f"  - {nombre_sucursal} ({familia}): Se esperan {total_registros_esperados} items. Calculadas {total_pages_calculadas} páginas.")

            parser = TableParser()
            parser.feed(initial_data['tabla'])
            if not headers and parser.headers:
                headers = parser.headers
            all_rows.extend(parser.rows)

            for page_num in range(2, total_pages_calculadas + 1):
                page_data = fetch_page_data(page_num, familia, id_sucursal)
                if page_data and page_data.get('tabla'):
                    parser = TableParser()
                    parser.feed(page_data['tabla'])
                    all_rows.extend(parser.rows)
                else:
                    print(f"    Advertencia: No se obtuvo tabla para {familia} en {nombre_sucursal}, página {page_num}. Posible fin de datos o error.")
            
            print(f"  - {nombre_sucursal} ({familia}): Total de registros obtenidos: {len(all_rows)}.")

            # Convertir filas a diccionarios y añadir a la lista consolidada
            for row in all_rows:
                product_dict = {headers[i]: item for i, item in enumerate(row)}
                product_dict['Tienda'] = nombre_sucursal
                product_dict['ID_Sucursal'] = id_sucursal
                all_products_from_store.append(product_dict)

        except Exception as e:
            print(f"    Ocurrió un error inesperado en {nombre_sucursal}: {e}")

    total_items_scraped_for_store = len(all_products_from_store)
    print(f"\n--- Resumen para {nombre_sucursal} ({id_sucursal}): Total de artículos encontrados: {total_items_scraped_for_store} ---")
    return all_products_from_store

