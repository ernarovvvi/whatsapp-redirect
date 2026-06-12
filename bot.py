"""
WhatsApp сілтемесін Telegram бот арқылы жаңарту.
Бот GitHub API арқылы config.json файлын жаңартады.

Орнату:
  pip install python-telegram-bot requests

Іске қосу:
  python bot.py

Қоршаған орта айнымалылары (.env файлында немесе тікелей):
  TELEGRAM_BOT_TOKEN  — @BotFather-ден алынған бот токені
  GITHUB_TOKEN        — GitHub Personal Access Token (repo scope)
  GITHUB_REPO         — ernarovvvi/whatsapp-redirect
  ADMIN_IDS           — рұқсат етілген Telegram user ID-лер (үтірмен бөлінген)
"""

import os
import json
import base64
import re
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

import requests
from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ── Logging ──
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ── Config ──
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
GITHUB_TOKEN       = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO        = os.getenv("GITHUB_REPO", "ernarovvvi/whatsapp-redirect")
ADMIN_IDS_RAW      = os.getenv("ADMIN_IDS", "")
CONFIG_PATH        = "config.json"

# Parse admin IDs
ADMIN_IDS = set()
if ADMIN_IDS_RAW:
    for x in ADMIN_IDS_RAW.split(","):
        x = x.strip()
        if x.isdigit():
            ADMIN_IDS.add(int(x))

# ── GitHub helpers ──
GH_API = "https://api.github.com"
GH_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def gh_get_file(path: str) -> Optional[dict]:
    """Fetch file info from GitHub (content + sha)."""
    url = f"{GH_API}/repos/{GITHUB_REPO}/contents/{path}"
    r = requests.get(url, headers=GH_HEADERS, timeout=15)
    if r.status_code == 200:
        return r.json()
    return None


def gh_update_file(path: str, content: str, message: str, sha: str) -> bool:
    """Update (or create) a file on GitHub."""
    url = f"{GH_API}/repos/{GITHUB_REPO}/contents/{path}"
    payload = {
        "message": message,
        "content": base64.b64encode(content.encode()).decode(),
        "sha": sha,
        "branch": "main",
    }
    r = requests.put(url, headers=GH_HEADERS, json=payload, timeout=15)
    return r.status_code in (200, 201)


def get_current_link() -> Optional[str]:
    """Get the current WhatsApp link from config.json."""
    info = gh_get_file(CONFIG_PATH)
    if not info:
        return None
    raw = base64.b64decode(info["content"]).decode()
    data = json.loads(raw)
    return data.get("whatsapp_link")


def update_link(new_link: str) -> Tuple[bool, str]:
    """Update WhatsApp link in config.json on GitHub."""
    info = gh_get_file(CONFIG_PATH)
    if not info:
        return False, "❌ GitHub-тан config.json табылмады"

    sha = info["sha"]
    now = datetime.now(timezone(timedelta(hours=5))).isoformat()

    new_config = json.dumps(
        {"whatsapp_link": new_link, "updated_at": now},
        indent=2,
        ensure_ascii=False,
    ) + "\n"

    ok = gh_update_file(
        CONFIG_PATH,
        new_config,
        f"🔄 Сілтеме жаңартылды: {now}",
        sha,
    )

    if ok:
        return True, f"✅ Сілтеме сәтті жаңартылды!\n\n🔗 Жаңа сілтеме:\n{new_link}\n\n🕐 Уақыты: {now}"
    return False, "❌ GitHub жаңарту сәтсіз болды"


def is_valid_wa_link(text: str) -> bool:
    """Check if text is a valid WhatsApp invite link."""
    return bool(re.match(r"https?://chat\.whatsapp\.com/[A-Za-z0-9]{10,}", text.strip()))


def is_admin(user_id: int) -> bool:
    """Check if user is authorized admin."""
    if not ADMIN_IDS:
        return True  # if no admins set, allow everyone
    return user_id in ADMIN_IDS


# ── Bot Handlers ──

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Бастапқы хабарлама."""
    user = update.effective_user
    text = (
        f"👋 Сәлем, {user.first_name}!\n\n"
        "Мен WhatsApp сілтемелерді басқару ботымын.\n\n"
        "📋 **Командалар:**\n"
        "/setlink `<сілтеме>` — жаңа WhatsApp сілтемесін орнату\n"
        "/current — қазіргі сілтемені көру\n"
        "/help — көмек\n\n"
        "Немесе WhatsApp сілтемесін тікелей жіберіңіз — мен автоматты жаңартамын."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Көмек."""
    text = (
        "📖 **Пайдалану нұсқаулығы**\n\n"
        "1️⃣ Жаңа сілтеме орнату:\n"
        "   `/setlink https://chat.whatsapp.com/XXXXX`\n\n"
        "2️⃣ Немесе сілтемені тікелей жіберіңіз:\n"
        "   `https://chat.whatsapp.com/XXXXX`\n\n"
        "3️⃣ Қазіргі сілтемені тексеру:\n"
        "   `/current`\n\n"
        "🌐 Редирект бет:\n"
        f"   `https://{GITHUB_REPO.split('/')[0]}.github.io/{GITHUB_REPO.split('/')[1]}/`\n\n"
        "⚡ Сілтеме жаңартылғаннан кейін бірден жұмыс істейді!"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_current(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Қазіргі сілтемені көрсету."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Сізге рұқсат жоқ.")
        return

    link = get_current_link()
    if link:
        site = f"https://{GITHUB_REPO.split('/')[0]}.github.io/{GITHUB_REPO.split('/')[1]}/"
        await update.message.reply_text(
            f"📌 **Қазіргі WhatsApp сілтеме:**\n{link}\n\n"
            f"🌐 **Редирект бет:**\n{site}",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text("❌ Сілтеме табылмады. config.json тексеріңіз.")


async def cmd_setlink(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Жаңа сілтеме орнату."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Сізге рұқсат жоқ.")
        return

    if not ctx.args:
        await update.message.reply_text(
            "⚠️ Сілтемені көрсетіңіз:\n`/setlink https://chat.whatsapp.com/XXXXX`",
            parse_mode="Markdown",
        )
        return

    link = ctx.args[0].strip()
    if not is_valid_wa_link(link):
        await update.message.reply_text(
            "❌ Қате формат!\n\nДұрыс формат:\n`https://chat.whatsapp.com/KkrfMNiwKnN...`",
            parse_mode="Markdown",
        )
        return

    await update.message.reply_text("⏳ Жаңартылуда...")

    ok, msg = update_link(link)
    await update.message.reply_text(msg)

    if ok:
        log.info(f"Link updated by {update.effective_user.id}: {link}")


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """WhatsApp сілтемесі тікелей жіберілген кезде."""
    if not is_admin(update.effective_user.id):
        return

    text = (update.message.text or "").strip()

    if is_valid_wa_link(text):
        await update.message.reply_text("⏳ Сілтеме жаңартылуда...")
        ok, msg = update_link(text)
        await update.message.reply_text(msg)
        if ok:
            log.info(f"Link updated by {update.effective_user.id}: {text}")


async def cmd_myid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Пайдаланушы ID-сін көрсету (admin орнату үшін)."""
    await update.message.reply_text(f"🆔 Сіздің Telegram ID: `{update.effective_user.id}`", parse_mode="Markdown")


# ── Main ──

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN орнатылмаған!")
        print("   export TELEGRAM_BOT_TOKEN='your-bot-token'")
        return

    if not GITHUB_TOKEN:
        print("❌ GITHUB_TOKEN орнатылмаған!")
        print("   export GITHUB_TOKEN='your-github-token'")
        return

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("current", cmd_current))
    app.add_handler(CommandHandler("setlink", cmd_setlink))
    app.add_handler(CommandHandler("myid", cmd_myid))

    # Auto-detect WhatsApp links in messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info("🤖 Бот іске қосылды!")
    log.info(f"📦 Repo: {GITHUB_REPO}")
    log.info(f"👮 Admins: {ADMIN_IDS or 'барлығына рұқсат'}")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
