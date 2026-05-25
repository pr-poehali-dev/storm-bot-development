"""
Утилита для регистрации webhook Telegram-бота «Шторм».
Вызывается один раз вручную после деплоя.
"""
import json
import os
import requests

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
WEBHOOK_URL = "https://functions.poehali.dev/2e2765bc-376d-4ef0-b440-4cc0ef6aad5c"

CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


def handler(event: dict, context) -> dict:
    """Регистрирует webhook Telegram-бота и возвращает статус."""
    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": CORS, "body": ""}

    # Устанавливаем webhook
    resp = requests.get(
        f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
        params={"url": WEBHOOK_URL, "drop_pending_updates": True},
        timeout=10,
    )
    result = resp.json()

    # Получаем текущий статус webhook
    info_resp = requests.get(
        f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo",
        timeout=10,
    )
    info = info_resp.json()

    return {
        "statusCode": 200,
        "headers": {**CORS, "Content-Type": "application/json"},
        "body": json.dumps({
            "set_webhook": result,
            "webhook_info": info,
        }, ensure_ascii=False),
    }
