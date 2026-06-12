"""
Vercel Serverless Function — Telegram Bot Webhook Handler.
Тегін, тұрақты, 24/7 жұмыс істейді.
"""

import json
import os
import base64
import re
import requests as req
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler


# ── Config ──
BOT_TOKEN    = os.getenv("TELEGRAM_BOT_TOKEN", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO  = os.getenv("GITHUB_REPO", "ernarovvvi/whatsapp-redirect")
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "")
CONFIG_PATH  = "config.json"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
GH_API = "https://api.github.com"
GH_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# Parse admin IDs
ADMIN_IDS = set()
if ADMIN_IDS_RAW:
    for x in ADMIN_IDS_RAW.split(","):
        x = x.strip()
        if x.isdigit():
            ADMIN_IDS.add(int(x))


def is_admin(user_id):
    if not ADMIN_IDS:
        return True
    return user_id in ADMIN_IDS


# ── Telegram helpers ──

def send_msg(chat_id, text):
    req.post(f"{TG_API}/sendMessage", json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }, timeout=10)


# ── GitHub helpers ──

def gh_get_file():
    r = req.get(f"{GH_API}/repos/{GITHUB_REPO}/contents/{CONFIG_PATH}",
                headers=GH_HEADERS, timeout=15)
    if r.status_code == 200:
        return r.json()
    return None


def gh_update_file(content, message, sha):
    r = req.put(
        f"{GH_API}/repos/{GITHUB_REPO}/contents/{CONFIG_PATH}",
        headers=GH_HEADERS,
        json={
            "message": message,
            "content": base64.b64encode(content.encode()).decode(),
            "sha": sha,
            "branch": "main",
        },
        timeout=15,
    )
    return r.status_code in (200, 201)


def get_current_link():
    info = gh_get_file()
    if not info:
        return None
    raw = base64.b64decode(info["content"]).decode()
    data = json.loads(raw)
    return data.get("whatsapp_link")


def update_link(new_link):
    info = gh_get_file()
    if not info:
        return False, "❌ GitHub-тан config.json табылмады"

    now = datetime.now(timezone(timedelta(hours=5))).isoformat()
    new_config = json.dumps(
        {"whatsapp_link": new_link, "updated_at": now},
        indent=2, ensure_ascii=False,
    ) + "\n"

    ok = gh_update_file(new_config, f"🔄 Сілтеме жаңартылды: {now}", info["sha"])
    if ok:
        return True, (
            f"✅ Сілтеме сәтті жаңартылды!\n\n"
            f"🔗 Жаңа сілтеме:\n{new_link}\n\n"
            f"🕐 Уақыты: {now}"
        )
    return False, "❌ GitHub жаңарту сәтсіз болды"


def is_valid_wa_link(text):
    return bool(re.match(r"https?://chat\.whatsapp\.com/[A-Za-z0-9]{10,}", text.strip()))


# ── Bot Logic ──

def process_update(update):
    msg = update.get("message")
    if not msg:
        return

    chat_id = msg["chat"]["id"]
    user_id = msg["from"]["id"]
    first_name = msg["from"].get("first_name", "")
    text = (msg.get("text") or "").strip()

    if not text:
        return

    # /start
    if text == "/start":
        send_msg(chat_id,
            f"👋 Сәлем, {first_name}!\n\n"
            "Мен WhatsApp сілтемелерді басқару ботымын.\n\n"
            "📋 *Командалар:*\n"
            "/setlink `<сілтеме>` — жаңа WhatsApp сілтемесін орнату\n"
            "/current — қазіргі сілтемені көру\n"
            "/myid — Telegram ID-ңізді білу\n"
            "/help — көмек"
        )
        return

    # /help
    if text == "/help":
        owner = GITHUB_REPO.split("/")[0]
        repo = GITHUB_REPO.split("/")[1]
        send_msg(chat_id,
            "📖 *Пайдалану нұсқаулығы*\n\n"
            "1️⃣ Жаңа сілтеме орнату:\n"
            "   `/setlink https://chat.whatsapp.com/XXXXX`\n\n"
            "2️⃣ Немесе сілтемені тікелей жіберіңіз:\n"
            "   `https://chat.whatsapp.com/XXXXX`\n\n"
            "3️⃣ Қазіргі сілтемені тексеру:\n"
            "   `/current`\n\n"
            f"🌐 Редирект бет:\n   `https://{owner}.github.io/{repo}/`\n\n"
            "⚡ Сілтеме жаңартылғаннан кейін бірден жұмыс істейді!"
        )
        return

    # /myid
    if text == "/myid":
        send_msg(chat_id, f"🆔 Сіздің Telegram ID: `{user_id}`")
        return

    # /current
    if text == "/current":
        if not is_admin(user_id):
            send_msg(chat_id, "⛔ Сізге рұқсат жоқ.")
            return
        link = get_current_link()
        if link:
            owner = GITHUB_REPO.split("/")[0]
            repo = GITHUB_REPO.split("/")[1]
            send_msg(chat_id,
                f"📌 *Қазіргі WhatsApp сілтеме:*\n{link}\n\n"
                f"🌐 *Редирект бет:*\nhttps://{owner}.github.io/{repo}/"
            )
        else:
            send_msg(chat_id, "❌ Сілтеме табылмады.")
        return

    # /setlink <url>
    if text.startswith("/setlink"):
        if not is_admin(user_id):
            send_msg(chat_id, "⛔ Сізге рұқсат жоқ.")
            return
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            send_msg(chat_id, "⚠️ Сілтемені көрсетіңіз:\n`/setlink https://chat.whatsapp.com/XXXXX`")
            return
        link = parts[1].strip()
        if not is_valid_wa_link(link):
            send_msg(chat_id, "❌ Қате формат!\n\nДұрыс: `https://chat.whatsapp.com/KkrfMNi...`")
            return
        send_msg(chat_id, "⏳ Жаңартылуда...")
        ok, result = update_link(link)
        send_msg(chat_id, result)
        return

    # Auto-detect WhatsApp link
    if is_valid_wa_link(text) and is_admin(user_id):
        send_msg(chat_id, "⏳ Сілтеме жаңартылуда...")
        ok, result = update_link(text)
        send_msg(chat_id, result)
        return


# ── Vercel Handler ──

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            update = json.loads(body)
            process_update(update)
        except Exception as e:
            print(f"Error: {e}")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "status": "ok",
            "bot": "WhatsApp Redirect Bot",
            "repo": GITHUB_REPO,
        }).encode())

    def log_message(self, format, *args):
        pass  # Suppress default logging
