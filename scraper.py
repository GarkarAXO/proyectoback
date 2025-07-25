import json
import csv
import urllib.request
import urllib.parse
from html.parser import HTMLParser

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

def fetch_page_data(page_number):
    url = 'https://efectimundo.com.mx/catalogo/consulta_catalogo.php?metodo=consulta_catalogo&salida=res&id_sucursal=214&ramo=&familia=CELULARES&tipo=&prenda=&marca=&modelo=&descripcion=&col_order='
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
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode('utf-8'))

def main():
    try:
        initial_data = fetch_page_data(1)
        total_pages = int(initial_data.get('pag_final', 1))
        
        all_rows = []
        parser = TableParser()
        parser.feed(initial_data['tabla'])
        headers = parser.headers
        all_rows.extend(parser.rows)
        
        for page_num in range(2, total_pages + 1):
            page_data = fetch_page_data(page_num)
            parser = TableParser()
            parser.feed(page_data['tabla'])
            all_rows.extend(parser.rows)
            
        with open('celulares.csv', 'w', newline='', encoding='utf-8') as csvfile:
            csvwriter = csv.writer(csvfile)
            csvwriter.writerow(headers)
            csvwriter.writerows(all_rows)
            
        print(f"Se han guardado {len(all_rows)} registros en celulares.csv")

    except urllib.error.URLError as e:
        print(f"Error de red: {e}")
    except (KeyError, ValueError) as e:
        print(f"Error al procesar los datos: {e}")

if __name__ == "__main__":
    main()