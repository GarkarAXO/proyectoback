import os
import json
import time
from dotenv import load_dotenv
from scraper_completo import obtener_imagenes_efectimundo
from slack_sdk import WebClient

# Cargar variables de entorno
load_dotenv()
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")

client = WebClient(token=SLACK_BOT_TOKEN)

# Orden de sucursales y familias
try:
    with open("config_orden_envio.json", "r", encoding="utf-8") as f:
        config_orden = json.load(f)
    FAMILIAS_ORDENADAS = config_orden.get("familias_ordenadas", [])
    SUCURSALES_ORDENADAS_MAP = config_orden.get("sucursales_ordenadas", {})
    SUCURSALES_ORDENADAS_LIST = list(SUCURSALES_ORDENADAS_MAP.values())
    # --- AGREGA TU CHANNEL_ID AQUÍ ---
    SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID") or "TU_CHANNEL_ID"
except Exception as e:
    FAMILIAS_ORDENADAS = []
    SUCURSALES_ORDENADAS_LIST = []
    SLACK_CHANNEL_ID = ""
    print(f"Advertencia al cargar el orden de envío: {e}")

# IA DESACTIVADA TEMPORALMENTE
def analyze_offer_with_openai(product_data, productos_modelo):
    return "Sí\nMotivo: IA desactivada temporalmente"

def format_slack_blocks(marca, modelo, articulo, q1, q3,
                        cantidad_rango_bajo, rango_bajo_str,
                        cantidad_dominante, cantidad_rango_alto, rango_alto_str,
                        openai_msg=None):
    blocks = []
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": (
                f":iphone: *¡Oferta detectada!*\n"
                f"*Marca:* {marca}\n"
                f"*Modelo:* {modelo}\n"
                f"*Prenda/SKU:* {articulo['SKU']}\n"
                f"*Descripción:* {articulo['Descripción']}\n"
                f"*Sucursal:* {articulo['Sucursal']}\n"
                f"*Precio en sucursal:* {articulo['Precio Promoción']}\n"
                f":dollar: *Margen estimado:* ${articulo.get('MargenVsDominanteMenor', 0):,.0f}\n"
                f":label: *Artículo en rango bajo ({cantidad_rango_bajo}):* {rango_bajo_str}\n"
                f":moneybag: *Rango de precio dominante ({cantidad_dominante}):* ${q1:,.0f} a ${q3:,.0f}\n"
                f":chart_with_upwards_trend: *Rango alto ({cantidad_rango_alto}):* {rango_alto_str}"
            )
        }
    })

    # Imagen
    img_url = None
    if "Imagenes" in articulo and isinstance(articulo["Imagenes"], list) and articulo["Imagenes"]:
        img_url = articulo["Imagenes"][0]
        if not (isinstance(img_url, str) and img_url.startswith("http")):
            img_url = None
    if not img_url:
        sku = articulo.get("SKU", "")
        imagenes = obtener_imagenes_efectimundo(sku)
        if imagenes and isinstance(imagenes, list) and imagenes[0].startswith("http"):
            img_url = imagenes[0]
    if img_url:
        blocks.append({
            "type": "image",
            "image_url": img_url,
            "alt_text": f"Imagen de {marca} {modelo}"
        })

    # --- BLOQUE DE BOTONES ---
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "✅ Aceptar oferta"},
                "style": "primary",
                "action_id": "aceptar_oferta",
                "value": json.dumps({
                    "sku": articulo["SKU"],
                    "marca": marca,
                    "modelo": modelo
                })
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "❌ Rechazar"},
                "style": "danger",
                "action_id": "rechazar_oferta",
                "value": json.dumps({
                    "sku": articulo["SKU"],
                    "marca": marca,
                    "modelo": modelo
                })
            }
        ]
    })

    if openai_msg:
        partes = openai_msg.split("\n", 1)
        decision = partes[0].strip()
        razon = partes[1].strip() if len(partes) > 1 else ""
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"🤖 *Análisis IA:* *{decision}*\n"
                    f"_{razon}_"
                )
            }
        })

    blocks.append({"type": "divider"})
    return blocks

def orden_key(articulo):
    familia = articulo.get("Familia", "")
    sucursal = articulo.get("Sucursal", "")
    precio = float(articulo.get("Precio Promoción", "0").replace("$", "").replace(",", "") or 0)
    familia_idx = FAMILIAS_ORDENADAS.index(familia) if familia in FAMILIAS_ORDENADAS else len(FAMILIAS_ORDENADAS)
    sucursal_idx = SUCURSALES_ORDENADAS_LIST.index(sucursal) if sucursal in SUCURSALES_ORDENADAS_LIST else len(SUCURSALES_ORDENADAS_LIST)
    return (familia_idx, sucursal_idx, precio)

def send_slack_notification(payload_blocks):
    if not SLACK_CHANNEL_ID:
        print("Error: SLACK_CHANNEL_ID no configurado.")
        return
    try:
        response = client.chat_postMessage(
            channel=SLACK_CHANNEL_ID,
            text="¡Oferta detectada!",  # Mensaje plano (se requiere por Slack, aunque solo se use blocks)
            blocks=payload_blocks
        )
        print("Mensaje enviado por bot:", response["ts"])
    except Exception as e:
        print("No se pudo enviar la notificación a Slack (bot):", e)

def notificar_gangas_encontradas(
    path_analisis="analisis_modelos.json",
    productos_por_modelo_path="productos_agrupados_por_modelo.json"
):
    with open(productos_por_modelo_path, "r", encoding="utf-8") as f:
        productos_por_modelo = json.load(f)
    with open(path_analisis, "r", encoding="utf-8") as f:
        analisis = json.load(f)
    ofertas_enviadas = 0
    articulos_a_enviar = []
    for modelo_key, info in analisis.items():
        if "::" in modelo_key:
            marca, modelo = modelo_key.split("::", 1)
        else:
            marca, modelo = "", modelo_key
        q1 = info.get("q1", 0)
        q3 = info.get("q3", 0)
        productos_modelo = productos_por_modelo.get(modelo_key, [])
        top_4 = info.get("top_4_mas_baratos", [])
        if not top_4 or not productos_modelo:
            continue
        precio_minimo = float(top_4[0]["Precio Promoción"].replace("$", "").replace(",", ""))
        rango_bajo_inicio = precio_minimo
        rango_bajo_fin = q1
        rango_bajo_str = f"${rango_bajo_inicio:,.0f} a ${rango_bajo_fin:,.0f}"
        cantidad_rango_bajo = sum(
            rango_bajo_inicio <= float(p["Precio Promoción"].replace("$", "").replace(",", "")) <= rango_bajo_fin
            for p in productos_modelo
        )
        cantidad_dominante = sum(
            q1 <= float(p["Precio Promoción"].replace("$", "").replace(",", "")) <= q3
            for p in productos_modelo
        )
        rango_alto_inicio = q3
        if productos_modelo:
            precio_maximo = max(float(p["Precio Promoción"].replace("$", "").replace(",", "")) for p in productos_modelo)
        else:
            precio_maximo = q3
        rango_alto_str = f"${rango_alto_inicio:,.0f} a ${precio_maximo:,.0f}"
        cantidad_rango_alto = sum(
            rango_alto_inicio < float(p["Precio Promoción"].replace("$", "").replace(",", "")) <= precio_maximo
            for p in productos_modelo
        )
        for articulo in top_4:
            articulos_a_enviar.append({
                "marca": marca,
                "modelo": modelo,
                "articulo": articulo,
                "q1": q1,
                "q3": q3,
                "cantidad_rango_bajo": cantidad_rango_bajo,
                "rango_bajo_str": rango_bajo_str,
                "cantidad_dominante": cantidad_dominante,
                "cantidad_rango_alto": cantidad_rango_alto,
                "rango_alto_str": rango_alto_str,
                "productos_modelo": productos_modelo
            })
    articulos_a_enviar.sort(key=lambda x: orden_key(x["articulo"]))
    for item in articulos_a_enviar:
        openai_msg = analyze_offer_with_openai(item["articulo"], item["productos_modelo"])
        if openai_msg.lower().startswith("sí") or openai_msg.lower().startswith("si"):
            blocks = format_slack_blocks(
                marca=item["marca"],
                modelo=item["modelo"],
                articulo=item["articulo"],
                q1=item["q1"],
                q3=item["q3"],
                cantidad_rango_bajo=item["cantidad_rango_bajo"],
                rango_bajo_str=item["rango_bajo_str"],
                cantidad_dominante=item["cantidad_dominante"],
                cantidad_rango_alto=item["cantidad_rango_alto"],
                rango_alto_str=item["rango_alto_str"],
                openai_msg=openai_msg
            )
            send_slack_notification(blocks)
            ofertas_enviadas += 1
            print(f"Oferta de {item['marca']} {item['modelo']} enviada a Slack (BOT). Esperando 3 minutos...")
            time.sleep(180)
        else:
            print(f"GANGA RECHAZADA POR IA (en envío): {item['marca']} {item['modelo']} {item['articulo']['SKU']} | {openai_msg}")
    print(f"Ofertas totales enviadas a Slack: {ofertas_enviadas}")
