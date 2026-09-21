import os
import re
import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import yt_dlp
from pydub import AudioSegment
import requests

# ------------------ تنظیمات ------------------
BOT_TOKEN = "8997153948:AAGeCopASjy92GEMuPx8c6vmoCVwhFry_OA"
ADMIN_ID = 8957805774
AUDD_TOKEN = "d78b1f04377ddcb73388d2d54a6ac26b"

# ------------------ لاگ ------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ------------------ توابع کمکی ------------------

def notify_admin(context: ContextTypes.DEFAULT_TYPE, text: str):
    try:
        context.bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"خطا در ارسال به ادمین: {e}")

def is_instagram_url(url: str) -> bool:
    return bool(re.search(r"(instagram\.com/(reel|p|tv)/)", url))

def download_instagram_video(url: str, output_path: str = "temp_video") -> str | None:
    ydl_opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": f"{output_path}.%(ext)s",
        "quiet": True,
        "no_warnings": True,
        # "cookiefile": "cookies.txt",
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            return filename
    except Exception as e:
        logger.error(f"خطا در دانلود ویدیو: {e}")
        return None

def extract_audio(video_path: str, audio_path: str = "temp_audio.mp3") -> str | None:
    try:
        audio = AudioSegment.from_file(video_path)
        audio = audio[:30000]
        audio.export(audio_path, format="mp3")
        return audio_path
    except Exception as e:
        logger.error(f"خطا در استخراج صدا: {e}")
        return None

def recognize_song(audio_path: str) -> dict | None:
    try:
        with open(audio_path, "rb") as f:
            data = {
                "api_token": AUDD_TOKEN,
                "return": "spotify,apple_music",
            }
            files = {"file": f}
            response = requests.post("https://api.audd.io/", data=data, files=files, timeout=30)
            result = response.json()

        if result.get("status") == "success" and result.get("result"):
            return result["result"]
        return None
    except Exception as e:
        logger.error(f"خطا در تشخیص آهنگ: {e}")
        return None

def cleanup(*files):
    for f in files:
        if f and os.path.exists(f):
            try:
                os.remove(f)
            except:
                pass

# ------------------ هندلرها ------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"👋 سلام {user.first_name}!\n\n"
        "لینک ریلز یا پست اینستاگرام رو بفرست تا ویدیوش رو برات بیارم.\n"
        "بعد می‌تونی با یک کلیک آهنگش رو هم پیدا کنی 🎵"
    )
    await update.message.reply_text(text)

    notify_admin(
        context,
        f"🟢 *استارت جدید*\n\n"
        f"👤 نام: {user.full_name}\n"
        f"🆔 آیدی: `{user.id}`\n"
        f"📱 یوزرنیم: @{user.username if user.username else 'ندارد'}\n"
        f"⏰ زمان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

async def handle_instagram_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    url = update.message.text.strip()

    if not is_instagram_url(url):
        await update.message.reply_text("❌ لطفاً فقط لینک ریلز یا پست اینستاگرام بفرست.")
        return

    notify_admin(
        context,
        f"📥 *درخواست جدید*\n\n"
        f"👤 {user.full_name} (`{user.id}`)\n"
        f"🔗 {url}"
    )

    status_msg = await update.message.reply_text("⏳ در حال دانلود ویدیو... لطفاً صبر کن")

    video_path = download_instagram_video(url)

    if not video_path or not os.path.exists(video_path):
        await status_msg.edit_text("❌ متأسفانه نتونستم ویدیو رو دانلود کنم.\nممکنه پست خصوصی باشه یا مشکل موقت باشه.")
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎵 پیدا کردن موزیک", callback_data=f"find_music|{video_path}")]
    ])

    try:
        with open(video_path, "rb") as video_file:
            await update.message.reply_video(
                video=video_file,
                caption="✅ ویدیو آماده شد\nروی دکمه زیر بزن تا آهنگش رو پیدا کنم.",
                reply_markup=keyboard,
                supports_streaming=True
            )
        await status_msg.delete()
    except Exception as e:
        logger.error(e)
        await status_msg.edit_text("❌ خطا در ارسال ویدیو")
        cleanup(video_path)

async def find_music_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    data = query.data

    if not data.startswith("find_music|"):
        return

    video_path = data.split("|", 1)[1]

    if not os.path.exists(video_path):
        await query.edit_message_caption(caption="❌ فایل ویدیو منقضی شده. لطفاً دوباره لینک بفرست.")
        return

    await query.edit_message_caption(caption="🔍 در حال جستجوی آهنگ... کمی صبر کن")

    notify_admin(
        context,
        f"🎵 *درخواست پیدا کردن موزیک*\n\n"
        f"👤 {user.full_name} (`{user.id}`)"
    )

    audio_path = extract_audio(video_path)

    if not audio_path:
        await query.edit_message_caption(caption="❌ خطا در استخراج صدا از ویدیو")
        cleanup(video_path)
        return

    song = recognize_song(audio_path)

    if not song:
        await query.edit_message_caption(caption="😕 آهنگی پیدا نشد.\nممکنه آهنگ اورجینال باشه یا نویز زیاد داشته باشه.")
        cleanup(video_path, audio_path)
        return

    title = song.get("title", "نامشخص")
    artist = song.get("artist", "نامشخص")
    caption = f"🎵 *{title}*\n👤 {artist}"

    try:
        with open(audio_path, "rb") as audio_file:
            await context.bot.send_audio(
                chat_id=query.message.chat_id,
                audio=audio_file,
                title=title,
                performer=artist,
                caption=caption,
                parse_mode="Markdown"
            )
        await query.edit_message_caption(caption=f"✅ آهنگ پیدا شد!\n\n🎵 {title}\n👤 {artist}")
    except Exception as e:
        logger.error(e)
        await query.edit_message_caption(caption="❌ خطا در ارسال فایل آهنگ")

    cleanup(video_path, audio_path)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Exception: {context.error}")

# ------------------ اجرای ربات ------------------

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_instagram_link))
    app.add_handler(CallbackQueryHandler(find_music_callback, pattern=r"^find_music\|"))
    app.add_error_handler(error_handler)

    print("🤖 ReelTuneBot (@ReelTune1Bot) در حال اجراست...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
