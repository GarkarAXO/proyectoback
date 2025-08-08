import os
import httpx
from dotenv import load_dotenv

load_dotenv()
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")

async def borrar_mensaje(channel_id, message_ts):
    url = "https://slack.com/api/chat.delete"
    headers = {
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "channel": channel_id,
        "ts": message_ts
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, data=data, headers=headers)
        print("Respuesta de Slack:", response.json())

if __name__ == "__main__":
    import asyncio
    
    # ⚠️ Cambia estos valores por un mensaje real enviado por tu bot
    CHANNEL_ID = "C098P8A6U2C"   # Ejemplo: canal donde está el mensaje
    MESSAGE_TS = "1754422536.172679"  # Ejemplo: ts del mensaje a borrar

    asyncio.run(borrar_mensaje(CHANNEL_ID, MESSAGE_TS))
