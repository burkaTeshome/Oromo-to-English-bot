import logging
import json
import os
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    InlineQueryHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from google.cloud import translate_v2 as translate
from google.auth.credentials import Credentials
from google.oauth2 import service_account

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize the Google Cloud Translate client
credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
if not credentials_json:
    raise ValueError("GOOGLE_CREDENTIALS_JSON environment variable not set")

try:
    credentials_info = json.loads(credentials_json)
    credentials = service_account.Credentials.from_service_account_info(
        credentials_info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    translator = translate.Client(credentials=credentials)
except json.JSONDecodeError as e:
    raise ValueError(f"Invalid GOOGLE_CREDENTIALS_JSON format: {e}")

# Define supported languages
SUPPORTED_LANGUAGES = {
    "om": "Afaan Oromo",
    "en": "English",
}

# Menu options
MENU_OPTIONS = [
    ["Afaan Oromo to English"],
    ["English to Afaan Oromo"],
]

# Feedback file
FEEDBACK_FILE = "/opt/render/project/src/feedback.log"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message and display the translation menu."""
    welcome_message = (
        "Welcome to the Afaan Oromo ↔ English Translator Bot!\n\n"
        "Please select a translation option or use inline mode with @YourBot <text>."
    )
    reply_markup = ReplyKeyboardMarkup(MENU_OPTIONS, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)
    context.user_data["state"] = "awaiting_menu_choice"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user messages based on the current state."""
    user_text = update.message.text
    user_state = context.user_data.get("state", "awaiting_menu_choice")

    if user_state == "awaiting_menu_choice":
        if user_text == "Afaan Oromo to English":
            context.user_data["source_lang"] = "om"
            context.user_data["target_lang"] = "en"
            await update.message.reply_text(
                "Please enter the word or sentence to translate from Afaan Oromo to English:",
                reply_markup=ReplyKeyboardRemove()
            )
            context.user_data["state"] = "awaiting_text"
        elif user_text == "English to Afaan Oromo":
            context.user_data["source_lang"] = "en"
            context.user_data["target_lang"] = "om"
            await update.message.reply_text(
                "Please enter the word or sentence to translate from English to Afaan Oromo:",
                reply_markup=ReplyKeyboardRemove()
            )
            context.user_data["state"] = "awaiting_text"
        else:
            await update.message.reply_text(
                "Please select a valid option from the menu:",
                reply_markup=ReplyKeyboardMarkup(MENU_OPTIONS, one_time_keyboard=True, resize_keyboard=True)
            )
    elif user_state == "awaiting_text":
        source_lang = context.user_data.get("source_lang")
        target_lang = context.user_data.get("target_lang")
        text = user_text

        try:
            result = translator.translate(text, source_language=source_lang, target_language=target_lang)
            translated_text = result["translatedText"]
            result_text = f"Original ({SUPPORTED_LANGUAGES[source_lang]}): {text}\n"
            result_text += f"Translated ({SUPPORTED_LANGUAGES[target_lang]}): {translated_text}"

            # Add rating buttons
            keyboard = [
                [
                    InlineKeyboardButton("👍 Good", callback_data=f"rate_good_{source_lang}_{target_lang}_{text}_{translated_text}"),
                    InlineKeyboardButton("👎 Poor", callback_data=f"rate_poor_{source_lang}_{target_lang}_{text}_{translated_text}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(result_text, reply_markup=reply_markup)

        except Exception as e:
            logger.error(f"Translation error: {e}")
            await update.message.reply_text("An error occurred during translation. Please try again.")

        # Return to menu
        await update.message.reply_text(
            "Please select a translation option:",
            reply_markup=ReplyKeyboardMarkup(MENU_OPTIONS, one_time_keyboard=True, resize_keyboard=True)
        )
        context.user_data["state"] = "awaiting_menu_choice"
        context.user_data.pop("source_lang", None)
        context.user_data.pop("target_lang", None)

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline queries."""
    query = update.inline_query.query
    if not query:
        return

    try:
        # Translate in both directions
        om_to_en = translator.translate(query, source_language="om", target_language="en")
        en_to_om = translator.translate(query, source_language="en", target_language="om")

        results = [
            InlineQueryResultArticle(
                id="om_to_en",
                title="Afaan Oromo to English",
                input_message_content=InputTextMessageContent(
                    f"Original (Afaan Oromo): {query}\nTranslated (English): {om_to_en['translatedText']}"
                ),
                description=om_to_en["translatedText"],
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("👍 Good", callback_data=f"rate_good_om_en_{query}_{om_to_en['translatedText']}"),
                        InlineKeyboardButton("👎 Poor", callback_data=f"rate_poor_om_en_{query}_{om_to_en['translatedText']}")
                    ]
                ])
            ),
            InlineQueryResultArticle(
                id="en_to_om",
                title="English to Afaan Oromo",
                input_message_content=InputTextMessageContent(
                    f"Original (English): {query}\nTranslated (Afaan Oromo): {en_to_om['translatedText']}"
                ),
                description=en_to_om["translatedText"],
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("👍 Good", callback_data=f"rate_good_en_om_{query}_{en_to_om['translatedText']}"),
                        InlineKeyboardButton("👎 Poor", callback_data=f"rate_poor_en_om_{query}_{en_to_om['translatedText']}")
                    ]
                ])
            )
        ]
        await update.inline_query.answer(results)
    except Exception as e:
        logger.error(f"Inline translation error: {e}")

async def handle_rating(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle rating button presses."""
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    username = query.from_user.username or "Unknown"

    try:
        # Parse callback data
        parts = data.split("_", 3)
        rating, source_lang, target_lang, rest = parts
        original_text, translated_text = rest.rsplit("_", 1)

        # Log feedback
        feedback = f"User: {username} (ID: {user_id}), Rating: {rating}, Source: {source_lang}, Target: {target_lang}, Original: {original_text}, Translated: {translated_text}\n"
        with open(FEEDBACK_FILE, "a") as f:
            f.write(feedback)

        await query.answer(f"Thank you for your {rating.replace('rate_', '')} rating!")
        await query.edit_message_text(query.message.text + f"\n\nRated: {rating.replace('rate_', '')}")
    except Exception as e:
        logger.error(f"Rating error: {e}")
        await query.answer("Error processing your rating.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors caused by updates."""
    logger.error(f"Update {update} caused error {context.error}")
    if update and update.message:
        await update.message.reply_text("An unexpected error occurred. Please try again.")

async def health_check(request):
    """Handle Render health check on root path."""
    return web.Response(status=200, text="OK")

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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(InlineQueryHandler(inline_query))
    app.add_handler(CallbackQueryHandler(handle_rating, pattern=r"^rate_(good|poor)_.*"))
    app.add_error_handler(error_handler)

    web_app = web.Application()
    web_app["bot"] = app
    web_app.router.add_post("/webhook", webhook)
    web_app.router.add_route("*", "/", health_check)  # Handle GET, HEAD, etc. for health check

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
        raise