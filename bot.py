import logging
import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from yt_dlp import YoutubeDL

BOT_TOKEN = "7938805493:AAHtOYzKjKgMy_TqUCqrx-yLvBWBq0OtF8A"
API_URL = "http://localhost:8000/search"

logging.basicConfig(level=logging.INFO)
user_results = {}

def format_duration(seconds):
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes}:{seconds:02}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎵 Введи назву пісні або посилання:")

async def handle_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    user_id = update.message.from_user.id

    if query.startswith("http"):
        await download_and_send(update, context, query, title="Твій трек")
        return

    try:
        response = requests.get(API_URL, params={"q": query})
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])
    except Exception as e:
        logging.error(f"[API ERROR] {e}")
        await update.message.reply_text("⚠Помилка при зверненні до API.")
        return

    if not results:
        await update.message.reply_text("Нічого не знайдено.")
        return

    user_results[user_id] = results

    keyboard = [
        [InlineKeyboardButton(f"{i+1}. {item['title']} ({format_duration(item['duration'])})", callback_data=f"select_{i}")]
        for i, item in enumerate(results)
    ]

    await update.message.reply_text(
        "🔍 Ось що я знайшов:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    index = int(query.data.split("_")[1])
    track = user_results.get(user_id, [])[index]

    await download_and_send(query.message, context, track["link"], track["title"])

async def download_and_send(message, context, link, title="🎶 Завантаження"):
    safe_title = "".join(c for c in title if c.isalnum() or c in " _-").strip()
    output_template = safe_title

    await message.reply_text(f"Завантажую: {title}...")

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_template,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'noplaylist': True,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            filepath = f"{output_template}.mp3"
            if os.path.exists(filepath):
                with open(filepath, "rb") as f:
                    await message.reply_audio(f, title=title)
                os.remove(filepath)
            else:
                await message.reply_text("Файл не знайдено після завантаження.")
    except Exception as e:
        logging.error(f"[YT-DLP ERROR] {e}")
        await message.reply_text("Помилка при завантаженні треку.")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_query))
    app.add_handler(CallbackQueryHandler(handle_selection))
    app.run_polling()

if __name__ == "__main__":
    main()
