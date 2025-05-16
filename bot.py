import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from googletrans import Translator, LANGUAGES
import os
from aiohttp import web

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize the translator
translator = Translator()

# Define supported languages
SUPPORTED_LANGUAGES = {
    "or": "Afaan Oromo",
    "en": "English",
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the /start command is issued."""
    welcome_message = (
        "Welcome to the Afaan Oromo ↔ English Translator Bot!\n\n"
        "To translate, send a message in this format:\n"
        "/translate <source_lang> <target_lang> <text>\n"
        "Example: /translate or en Salaam\n"
        "Supported languages:\n"
        "- or: Afaan Oromo\n"
        "- en: English\n\n"
        "Or simply send text, and I'll ask for translation directions."
    )
    await update.message.reply_text(welcome_message)

async def translate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /translate command."""
    try:
        args = context.args
        if len(args) < 3:
            await update.message.reply_text(
                "Please use the format: /translate <source_lang> <target_lang> <text>\n"
                "Example: /translate or en Salaam"
            )
            return

        source_lang = args[0].lower()
        target_lang = args[1].lower()
        text = " ".join(args[2:])

        if source_lang not in SUPPORTED_LANGUAGES or target_lang not in SUPPORTED_LANGUAGES:
            await update.message.reply_text(
                "Unsupported language. Use 'or' for Afaan Oromo or 'en' for English."
            )
            return

        if not text:
            await update.message.reply_text("Please provide text to translate.")
            return

        translated = translator.translate(text, src=source_lang, dest=target_lang)
        result = f"Original ({SUPPORTED_LANGUAGES[source_lang]}): {text}\n"
        result += f"Translated ({SUPPORTED_LANGUAGES[target_lang]}): {translated.text}"
        await update.message.reply_text(result)

    except Exception as e:
        logger.error(f"Translation error: {e}")
        await update.message.reply_text("An error occurred during translation. Please try again.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle plain text messages and ask for translation direction."""
    text = update.message.text
    context.user_data["pending_text"] = text
    await update.message.reply_text(
        "Please specify the translation direction:\n"
        "1. Afaan Oromo to English: /to_en\n"
        "2. English to Afaan Oromo: /to_or"
    )

async def to_en(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Translate stored text to English."""
    text = context.user_data.get("pending_text")
    if not text:
        await update.message.reply_text("No text to translate. Please send some text first.")
        return

    try:
        translated = translator.translate(text, src="or", dest="en")
        result = f"Original (Afaan Oromo): {text}\nTranslated (English): {translated.text}"
        await update.message.reply_text(result)
        context.user_data.pop("pending_text", None)
    except Exception as e:
        logger.error(f"Translation error: {e}")
        await update.message.reply_text("An error occurred during translation. Please try again.")

async def to_or(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Translate stored text to Afaan Oromo."""
    text = context.user_data.get("pending_text")
    if not text:
        await update.message.reply_text("No text to translate. Please send some text first.")
        return

    try:
        translated = translator.translate(text, src="en", dest="or")
        result = f"Original (English): {text}\nTranslated (Afaan Oromo): {translated.text}"
        await update.message.reply_text(result)
        context.user_data.pop("pending_text", None)
    except Exception as e:
        logger.error(f"Translation error: {e}")
        await update.message.reply_text("An error occurred during translation. Please try again.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors caused by updates."""
    logger.error(f"Update {update} caused error {context.error}")
    if update:
        await update.message.reply_text("An unexpected error occurred. Please try again.")

async def webhook(request):
    """Handle incoming webhook updates."""
    app = request.app["bot"]
    update = Update.de_json(await request.json(), app.bot)
    await app.process_update(update)
    return web.Response()

async def main():
    """Set up and start the bot with webhook."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set")

    port = int(os.getenv("PORT", 10000))  # Default to 10000 for Render
    logger.info(f"Starting webhook server on port {port}")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("translate", translate))
    app.add_handler(CommandHandler("to_en", to_en))
    app.add_handler(CommandHandler("to_or", to_or))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(error_handler)

    web_app = web.Application()
    web_app["bot"] = app
    web_app.router.add_post("/webhook", webhook)

    await app.initialize()
    await app.start()

    return web_app, port

if __name__ == "__main__":
    import asyncio
    from aiohttp import web

    async def start_server():
        web_app, port = await main()
        runner = web.AppRunner(web_app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        logger.info(f"Binding to port {port}")
        await site.start()
        logger.info(f"Server started on http://0.0.0.0:{port}/webhook")
        await asyncio.Event().wait()

    try:
        asyncio.run(start_server())
    except KeyboardInterrupt:
        logger.info("Shutting down server")
    except Exception as e:
        logger.error(f"Server error: {e}")