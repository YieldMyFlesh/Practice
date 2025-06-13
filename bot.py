import logging
import os
import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
from yt_dlp import YoutubeDL

BOT_TOKEN = "7938805493:AAHtOYzKjKgMy_TqUCqrx-yLvBWBq0OtF8A"
API_URL = "http://localhost:8000/search"

logging.basicConfig(level=logging.INFO)
user_results = {}

def seconds_to_time(seconds):
    minutes = int(seconds // 60)
    sec = int(seconds % 60)
    return f"{minutes}:{sec:02d}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отправь название песни или ссылку на YouTube.")

async def send_mp3(update: Update, url: str):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'noplaylist': True,
    }
    os.makedirs('downloads', exist_ok=True)

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        mp3_filename = os.path.splitext(filename)[0] + ".mp3"

    with open(mp3_filename, 'rb') as audio:
        await update.message.reply_audio(audio=audio, title=info.get('title'))

    # Удаляем скачанные файлы, чтобы не занимать место
    try:
        os.remove(mp3_filename)
        if os.path.exists(filename):
            os.remove(filename)
    except Exception as e:
        logging.warning(f"Не удалось удалить файлы: {e}")

async def handle_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    user_id = update.message.from_user.id

    if query.startswith("http"):
        await update.message.reply_text("Скачиваю аудио, подожди...")
        try:
            await send_mp3(update, query)
        except Exception as e:
            logging.error(f"Ошибка при скачивании mp3: {e}")
            await update.message.reply_text("Не удалось скачать аудио.")
        return

    # Иначе ищем по названию через FastAPI
    try:
        resp = requests.get(API_URL, params={"q": query}, timeout=10)
        data = resp.json().get("results", [])
    except Exception as e:
        logging.error(f"[API ERROR] {e}")
        return await update.message.reply_text("Ошибка API или yt_dlp. Попробуй позже.")

    if not data:
        return await update.message.reply_text("Ничего не найдено :(")

    user_results[user_id] = data

    keyboard = [[
        InlineKeyboardButton(
            f"{i+1}. {item['title']} ({seconds_to_time(item['duration'])})",
            callback_data=f"link_{item['link']}"
        )
    ] for i, item in enumerate(data)]

    await update.message.reply_text(
        "Вот что я нашёл. Нажми на песню, чтобы скачать MP3:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data.startswith("link_"):
        link = query.data[5:]
        await query.message.reply_text("Скачиваю аудио, подожди...")
        try:
            # Отправляем mp3 пользователю
            await send_mp3(query.message, link)
        except Exception as e:
            logging.error(f"Ошибка при скачивании mp3: {e}")
            await query.message.reply_text("Не удалось скачать аудио.")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_query))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.run_polling()

if __name__ == "__main__":
    main()
