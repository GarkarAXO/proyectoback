import re

def clean_price_str(price_str):
    """
    Limpia una cadena de precio (ej: '$ 6,599.00') y la convierte en float.
    Si falla, regresa 0.0.
    """
    if not isinstance(price_str, str):
        price_str = str(price_str)
    # Elimina cualquier carácter que no sea dígito o punto decimal
    cleaned_str = re.sub(r'[^\d.]', '', price_str.replace(',', ''))
    try:
        return float(cleaned_str)
    except (ValueError, AttributeError):
        return 0.0
