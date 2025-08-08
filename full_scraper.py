import json
import urllib.request
import urllib.parse
import requests
import os
from html.parser import HTMLParser

OUTPUT_JSON = "grouped_products_by_model.json"

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

def fetch_page_data(page_number, category, store_id):
    category_encoded = urllib.parse.quote(category)
    url = f'https://efectimundo.com.mx/catalogo/consulta_catalogo.php?metodo=consulta_catalogo&salida=res&id_sucursal={store_id}&ramo=&familia={category_encoded}&tipo=&prenda=&marca=&modelo=&descripcion=&col_order='
    headers = {
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'es-419,es;q=0.6',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Origin': 'https://efectimundo.com.mx',
        'Pragma': 'no-cache',
        'Referer': 'https://efectimundo.com.mx/catalogo/catalogo.php',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        'X-Requested-With': 'XMLHttpRequest'
    }
    data = urllib.parse.urlencode({'pagina': page_number}).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            response_content = response.read().decode('utf-8')
            parsed_json = json.loads(response_content)
            return parsed_json
    except Exception as e:
        print(f"Error al obtener página {page_number} de {category} en sucursal {store_id}: {e}")
        return None

def scrape_store_by_categories(store_id, store_name, categories):
    all_products = []
    for category in categories:
        all_rows = []
        headers = []

        print(f"Procesando {category} en {store_name} ({store_id})")

        try:
            initial_data = fetch_page_data(1, category, store_id)
            if not initial_data or not initial_data.get('tabla'):
                print(f"No hay datos para {category} en {store_name}.")
                continue

            total_items = int(initial_data.get('rowCount', 0))
            page_size = 50
            total_pages = (total_items + page_size - 1) // page_size

            parser = TableParser()
            parser.feed(initial_data['tabla'])
            headers = parser.headers
            all_rows.extend(parser.rows)

            for page_num in range(2, total_pages + 1):
                data = fetch_page_data(page_num, category, store_id)
                if data and data.get("tabla"):
                    parser = TableParser()
                    parser.feed(data["tabla"])
                    all_rows.extend(parser.rows)

            for row in all_rows:
                product = {headers[j]: item for j, item in enumerate(row)}
                description = product.get("Descripción", "").lower()
                product_type = product.get("Tipo", "").lower()

                if (
                    "dañado" in description or "dañad" in description or "daniado" in description or
                    "broken" in description or product_type == "con_reporte" or
                    "dañado" in product_type or "broken" in product_type
                ):
                    continue

                promo_price = product.get("Precio Promoción", "").replace("$", "").replace(",", "").strip()
                try:
                    if not promo_price or float(promo_price) <= 0:
                        continue
                except Exception:
                    continue

                clean_product = {
                    "SKU": product.get("Prenda / Sku Lote", "").strip(),
                    "Marca": product.get("Marca", "").strip(),
                    "Modelo": product.get("Modelo", "").strip(),
                    "Descripción": product.get("Descripción", "").strip(),
                    "Precio Promoción": product.get("Precio Promoción", "").strip(),
                    "Sucursal": store_name.strip()
                }

                all_products.append(clean_product)

        except Exception as e:
            print(f"Error al procesar {category} en {store_name}: {e}")

    return all_products

def group_and_save_by_model(products, output_path=OUTPUT_JSON):
    grouped = {}
    for p in products:
        brand = p.get('Marca', '').strip().upper()
        model = p.get('Modelo', '').strip().upper()
        key = f"{brand}::{model}"

        price_str = p.get("Precio Promoción", "").replace("$", "").replace(",", "").strip()
        try:
            price = float(price_str)
        except Exception:
            continue
        if price <= 0:
            continue

        if key not in grouped:
            grouped[key] = []
        grouped[key].append((price, p))

    sorted_grouped = {
        key: [prod for price, prod in sorted(items, key=lambda x: x[0])]
        for key, items in grouped.items()
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sorted_grouped, f, indent=2, ensure_ascii=False)
    print(f"\nProductos agrupados y guardados en {output_path}")

def get_images_by_sku(sku):
    url = "https://efectimundo.com.mx/catalogo/consulta_catalogo.php"
    params = {
        "metodo": "guardayMuestaImagenes",
        "prenda": sku
    }
    try:
        response = requests.post(url, params=params, timeout=5)
        data = response.json()

        if data.get("estatus") and "listaImagenes" in data:
            return [
                "https://efectimundo.com.mx/catalogo" + img.get("href", "").lstrip(".")
                for img in data["listaImagenes"]
                if isinstance(img, dict) and "href" in img
            ]
    except Exception as e:
        print(f"Error al obtener imagen para SKU {sku}: {e}")

    return []
