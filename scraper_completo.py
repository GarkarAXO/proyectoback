import json
import urllib.request
import urllib.parse
import requests
import os
from html.parser import HTMLParser

OUTPUT_JSON = "productos_agrupados_por_modelo.json"

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
        print(f"Error al obtener página {page_number} de {familia} en sucursal {id_sucursal}: {e}")
        return None

def scrape_store_for_families(id_sucursal, nombre_sucursal, familias):
    all_products_from_store = []
    for familia in familias:
        all_rows = []
        headers = []

        print(f"Procesando {familia} en {nombre_sucursal} ({id_sucursal})")

        try:
            initial_data = fetch_page_data(1, familia, id_sucursal)
            if not initial_data or not initial_data.get('tabla'):
                print(f"No hay datos para {familia} en {nombre_sucursal}.")
                continue

            total_pages = int(initial_data.get('pag_final', 1))
            page_size = 50
            total_items = int(initial_data.get('rowCount', 0))
            pages = (total_items + page_size - 1) // page_size

            parser = TableParser()
            parser.feed(initial_data['tabla'])
            headers = parser.headers
            all_rows.extend(parser.rows)

            for page_num in range(2, pages + 1):
                data = fetch_page_data(page_num, familia, id_sucursal)
                if data and data.get("tabla"):
                    parser = TableParser()
                    parser.feed(data["tabla"])
                    all_rows.extend(parser.rows)

            for row in all_rows:
                product_dict = {headers[j]: item for j, item in enumerate(row)}
                descripcion = product_dict.get("Descripción", "").lower()
                tipo = product_dict.get("Tipo", "").lower()

                # Filtro de productos dañados o sin precio válido
                if (
                    "dañado" in descripcion or "dañad" in descripcion or "daniado" in descripcion or
                    "broken" in descripcion or tipo == "con_reporte" or
                    "dañado" in tipo or "broken" in tipo
                ):
                    continue

                precio_promocion = product_dict.get("Precio Promoción", "").replace("$", "").replace(",", "").strip()
                try:
                    if not precio_promocion or float(precio_promocion) <= 0:
                        continue
                except Exception:
                    continue

                producto_limpio = {
                    "SKU": product_dict.get("Prenda / Sku Lote", "").strip(),
                    "Marca": product_dict.get("Marca", "").strip(),
                    "Modelo": product_dict.get("Modelo", "").strip(),
                    "Descripción": product_dict.get("Descripción", "").strip(),
                    "Precio Promoción": product_dict.get("Precio Promoción", "").strip(),
                    "Sucursal": nombre_sucursal.strip()
                }

                all_products_from_store.append(producto_limpio)

        except Exception as e:
            print(f"Error al procesar {familia} en {nombre_sucursal}: {e}")

    return all_products_from_store

def agrupar_y_guardar_por_modelo(productos, output_path=OUTPUT_JSON):
    agrupados = {}
    for p in productos:
        marca = p.get('Marca', '').strip().upper()
        modelo = p.get('Modelo', '').strip().upper()
        clave = f"{marca}::{modelo}"

        precio_str = p.get("Precio Promoción", "").replace("$", "").replace(",", "").strip()
        try:
            precio = float(precio_str)
        except Exception:
            continue
        if precio <= 0:
            continue  # Solo precios válidos

        if clave not in agrupados:
            agrupados[clave] = []
        agrupados[clave].append((precio, p))

    # Ordena de menor a mayor precio cada grupo
    agrupados_ordenados = {
        clave: [prod for precio, prod in sorted(lista, key=lambda x: x[0])]
        for clave, lista in agrupados.items()
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(agrupados_ordenados, f, indent=2, ensure_ascii=False)
    print(f"\nProductos agrupados y guardados en {output_path}")

# ---- FUNCIÓN PARA OBTENER IMÁGENES POR SKU ----
def obtener_imagenes_efectimundo(sku):
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

# ---------- EJEMPLO DE USO -----------
# all_products = scrape_store_for_families("01", "SUCURSAL CENTRO", ["Consolas", "Celulares", "Pantallas"])
# agrupar_y_guardar_por_modelo(all_products)
# imagenes = obtener_imagenes_efectimundo("123456")
# print(imagenes)
