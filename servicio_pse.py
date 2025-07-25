import os
import json
import urllib.request
import urllib.parse
import datetime
import re
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def clean_price_str(price_str):
    cleaned_str = re.sub(r'[^\d.]', '', price_str)
    try:
        return float(cleaned_str)
    except (ValueError, AttributeError):
        return 0.0

def get_real_comparison_data(product_data):
    print("DEBUG: Usando datos de comparación simulados (PSE deshabilitado).")
    return simulate_comparison_data(product_data['Precio Venta'])
