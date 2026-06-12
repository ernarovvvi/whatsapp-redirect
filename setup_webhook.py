"""
Telegram webhook-ты орнату скрипті.
Vercel-ге deploy жасағаннан кейін бір рет іске қосыңыз.

Қолдану:
  python setup_webhook.py <VERCEL_URL>

Мысалы:
  python setup_webhook.py https://whatsapp-redirect-xxx.vercel.app
"""

import sys
import requests

BOT_TOKEN = "8879509728:AAFNLUfpBbsmu2MnzJVrEazqRd5NbhV9bgM"
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def setup_webhook(vercel_url):
    webhook_url = f"{vercel_url}/api/webhook"

    # Delete old webhook
    r = requests.post(f"{TG_API}/deleteWebhook", timeout=10)
    print(f"Delete old webhook: {r.json()}")

    # Set new webhook
    r = requests.post(f"{TG_API}/setWebhook", json={
        "url": webhook_url,
        "allowed_updates": ["message"],
        "drop_pending_updates": True,
    }, timeout=10)

    result = r.json()
    if result.get("ok"):
        print(f"✅ Webhook сәтті орнатылды!")
        print(f"🔗 URL: {webhook_url}")
    else:
        print(f"❌ Қате: {result}")

    # Check webhook info
    r = requests.get(f"{TG_API}/getWebhookInfo", timeout=10)
    info = r.json().get("result", {})
    print(f"\n📋 Webhook ақпараты:")
    print(f"   URL: {info.get('url')}")
    print(f"   Pending: {info.get('pending_update_count', 0)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Қолдану: python setup_webhook.py <VERCEL_URL>")
        print("Мысалы:  python setup_webhook.py https://whatsapp-redirect-xxx.vercel.app")
        sys.exit(1)

    setup_webhook(sys.argv[1].rstrip("/"))
