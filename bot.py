import logging
import os
import requests
from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    Update, InputMediaPhoto
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from yt_dlp import YoutubeDL

BOT_TOKEN = "7938805493:AAHtOYzKjKgMy_TqUCqrx-yLvBWBq0OtF8A"
API_URL = "http://localhost:8000/search"

logging.basicConfig(level=logging.INFO)
user_results = {}

YDL_OPTS_BASE = {
    'format': 'bestaudio/best',
    'quiet': True,
    'noplaylist': True,
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }]
}


def seconds_to_time(seconds):
    minutes = int(seconds // 60)
    sec = int(seconds % 60)
    return f"{minutes}:{sec:02d}"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите название песни для поиска или ссылку на Youtube ролик.")


async def handle_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = update.message.text.strip()
    user_id = update.message.from_user.id

    if "youtube.com" in query_text or "youtu.be" in query_text:
        return await send_preview(update, context, link=query_text)

    try:
        resp = requests.get(API_URL, params={"q": query_text})
        resp.raise_for_status()
        data = resp.json().get("results", [])
    except Exception as e:
        logging.error(f"[API] {e}")
        return await update.message.reply_text("АПИ умерло, сорри лил бро.")

    if not data:
        return await update.message.reply_text("Ничего не найдено:(")

    user_results[user_id] = data

    keyboard = [[
        InlineKeyboardButton(
            f"{i+1}. {item['title']} ({seconds_to_time(item.get('duration', 0))})",
            callback_data=f"select_{i}"
        )
    ] for i, item in enumerate(data)]

    await update.message.reply_text(
        "вот, что я нашёл:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    index = int(query.data.split("_")[1])
    track = user_results.get(user_id, [])[index]
    await send_preview(query, context, link=track["link"], track_data=track)


async def send_preview(source, context, link, track_data=None):
    if not track_data:
        with YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(link, download=False)
        track_data = {
            "title": info.get("title", "без названия"),
            "duration": info.get("duration", 0),
            "thumbnail": info.get("thumbnails", [{}])[-1].get("url", ""),
            "link": link
        }

    caption = f"🎵 <b>{track_data['title']}</b>\n🕒 {seconds_to_time(track_data['duration'])}"
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🎧 MP3", callback_data=f"download_mp3|{link}"),
        InlineKeyboardButton("🔙 Назад", callback_data="back_to_list"),
        InlineKeyboardButton("🎞️ MP4", callback_data=f"download_mp4|{link}")
    ]])

    if hasattr(source, "edit_message_media"):
        await source.edit_message_media(
            media=InputMediaPhoto(media=track_data["thumbnail"], caption=caption, parse_mode="HTML"),
            reply_markup=keyboard
        )
    else:
        await source.message.reply_photo(
            photo=track_data["thumbnail"],
            caption=caption,
            parse_mode="HTML",
            reply_markup=keyboard
        )


async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "back_to_list":
        user_id = query.from_user.id
        results = user_results.get(user_id, [])
        keyboard = [[
            InlineKeyboardButton(
                f"{i+1}. {item['title']} ({seconds_to_time(item.get('duration', 0))})",
                callback_data=f"select_{i}"
            )
        ] for i, item in enumerate(results)]
        return await query.edit_message_text("🔙вернуться к списку", reply_markup=InlineKeyboardMarkup(keyboard))

    format_type, link = data.split("|")
    audio = format_type == "download_mp3"

    ydl_opts = YDL_OPTS_BASE.copy() if audio else {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': 'video.%(ext)s',
        'quiet': True,
        'noplaylist': True
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            file_name = ydl.prepare_filename(info)
            if audio:
                file_name = os.path.splitext(file_name)[0] + ".mp3"

        with open(file_name, "rb") as f:
            if audio:
                await query.message.reply_audio(f)
            else:
                await query.message.reply_video(f)

        os.remove(file_name)
    except Exception as e:
        logging.error(f"[DOWNLOAD ERROR] {e}")
        await query.message.reply_text("ошибка при загрузке трека.")


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_query))
    app.add_handler(CallbackQueryHandler(handle_selection, pattern=r"^select_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_download, pattern=r"^(download_mp3|download_mp4)\|.+|back_to_list$"))
    app.run_polling()


if __name__ == "__main__":
    main()
