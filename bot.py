import logging
import json
import os
import uuid
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
from datetime import datetime

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
    ["🌐 Afaan Oromo to English", "🌐 English to Afaan Oromo"],
    ["🔄 Restart (/start)", "📚 Help (/help)"],
    ["🕰️ History (/history)"],
]

# Feedback file
FEEDBACK_FILE = "/opt/render/project/src/feedback.log"

# Maximum history entries per user
HISTORY_LIMIT = 5

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message and display the enhanced menu."""
    welcome_message = (
        "🌍 *Afaan Oromo - English Translator Bot* 🌍\n\n"
        "Welcome! This bot translates between Afaan Oromo and English. Choose an option below:\n\n"
        "- 🌐 Translate using menu or inline mode (@YourBot <text>)\n"
        "- 📚 Get help with /help\n"
        "- 🕰️ View recent translations with /history\n\n"
        "Select an option:"
    )
    reply_markup = ReplyKeyboardMarkup(MENU_OPTIONS, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(welcome_message, parse_mode="Markdown", reply_markup=reply_markup)
    context.user_data["state"] = "awaiting_menu_choice"
    if "translation_history" not in context.user_data:
        context.user_data["translation_history"] = []

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Provide help instructions and start an interactive tutorial."""
    help_message = (
        "📚 *Afaan Oromo - English Translator Bot Help* 📚\n\n"
        "This bot translates between Afaan Oromo and English:\n"
        "- 🌐 *Menu Mode*: Use /start, choose an option, enter text.\n"
        "- 🚀 *Inline Mode*: Type @YourBot <text> (e.g., @YourBot Salaam).\n"
        "- 👍 *Rate Translations*: Click thumbs up or down after translations.\n"
        "- 🕰️ *History*: Use /history to view your last 5 translations.\n"
        "- 📚 *Help*: Use /help to see this message.\n\n"
        "Try a tutorial! Select a translation option:"
    )
    reply_markup = ReplyKeyboardMarkup(MENU_OPTIONS, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(help_message, parse_mode="Markdown", reply_markup=reply_markup)
    context.user_data["state"] = "tutorial_menu_choice"

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display the user's recent translations."""
    history = context.user_data.get("translation_history", [])
    if not history:
        await update.message.reply_text("🕰️ No translations yet. Try translating something first!")
        return

    history_message = "🕰️ *Your Recent Translations (up to 5)*:\n\n"
    for idx, entry in enumerate(history, 1):
        source_lang = SUPPORTED_LANGUAGES[entry['source_lang']]
        target_lang = SUPPORTED_LANGUAGES[entry['target_lang']]
        history_message += f"{idx}. *Original* ({source_lang}): {entry['original_text']}\n"
        history_message += f"   *Translated* ({target_lang}): {entry['translated_text']}\n"
        history_message += f"   *Time*: {entry['timestamp']}\n\n"
    await update.message.reply_text(history_message, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user messages based on the current state."""
    user_text = update.message.text.strip()
    user_state = context.user_data.get("state", "awaiting_menu_choice")

    if user_state in ["awaiting_menu_choice", "tutorial_menu_choice"]:
        is_tutorial = user_state == "tutorial_menu_choice"
        if user_text == "🌐 Afaan Oromo to English":
            context.user_data["source_lang"] = "om"
            context.user_data["target_lang"] = "en"
            prompt = "🌐 Enter a word or sentence to translate from Afaan Oromo to English (e.g., 'Salaam'):"
            if is_tutorial:
                prompt += "\n\n📚 *Tutorial*: Try a word like 'Salaam' to see how it works!"
            await update.message.reply_text(prompt, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
            context.user_data["state"] = "awaiting_text" if not is_tutorial else "tutorial_awaiting_text"
        elif user_text == "🌐 English to Afaan Oromo":
            context.user_data["source_lang"] = "en"
            context.user_data["target_lang"] = "om"
            prompt = "🌐 Enter a word or sentence to translate from English to Afaan Oromo (e.g., 'Hello'):"
            if is_tutorial:
                prompt += "\n\n📚 *Tutorial*: Try a word like 'Hello' to see how it works!"
            await update.message.reply_text(prompt, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
            context.user_data["state"] = "awaiting_text" if not is_tutorial else "tutorial_awaiting_text"
        elif user_text == "🔄 Restart (/start)":
            await start(update, context)
        elif user_text == "📚 Help (/help)":
            await help_command(update, context)
        elif user_text == "🕰️ History (/history)":
            await history(update, context)
        else:
            await update.message.reply_text(
                "❌ Please select a valid option from the menu:",
                reply_markup=ReplyKeyboardMarkup(MENU_OPTIONS, one_time_keyboard=True, resize_keyboard=True)
            )
            context.user_data["state"] = "awaiting_menu_choice"
    elif user_state in ["awaiting_text", "tutorial_awaiting_text"]:
        is_tutorial = user_state == "tutorial_awaiting_text"
        source_lang = context.user_data.get("source_lang")
        target_lang = context.user_data.get("target_lang")
        text = user_text

        if not text:
            await update.message.reply_text("❌ Please enter a non-empty word or sentence to translate.")
            return

        try:
            result = translator.translate(text, source_language=source_lang, target_language=target_lang)
            translated_text = result["translatedText"]
            result_text = f"*Original* ({SUPPORTED_LANGUAGES[source_lang]}): {text}\n"
            result_text += f"*Translated* ({SUPPORTED_LANGUAGES[target_lang]}): {translated_text}"

            history = context.user_data.get("translation_history", [])
            history.append({
                "source_lang": source_lang,
                "target_lang": target_lang,
                "original_text": text,
                "translated_text": translated_text,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            context.user_data["translation_history"] = history[-HISTORY_LIMIT:]

            # Generate unique translation ID
            translation_id = str(uuid.uuid4())
            context.user_data.setdefault("translation_records", {})[translation_id] = {
                "original_text": text,
                "translated_text": translated_text,
                "source_lang": source_lang,
                "target_lang": target_lang
            }

            keyboard = [
                [
                    InlineKeyboardButton("👍 Good", callback_data=f"rate_good_{source_lang}_{target_lang}_{translation_id}_0"),
                    InlineKeyboardButton("👎 Poor", callback_data=f"rate_poor_{source_lang}_{target_lang}_{translation_id}_0")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(result_text, parse_mode="Markdown", reply_markup=reply_markup)

            if is_tutorial:
                tutorial_message = (
                    "🎉 *Great!* You translated a word. Now try these:\n"
                    "- 👍 Rate the translation using thumbs up or down.\n"
                    "- 🕰️ Use /history to see your recent translations.\n"
                    "- 🚀 Try inline mode by typing @YourBot Salaam in any chat.\n"
                    "- 🔄 Use /start to return to the menu.\n\n"
                    "📚 *Tutorial complete!* Use /help to repeat this guide."
                )
                await update.message.reply_text(tutorial_message, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Translation error: {e}")
            await update.message.reply_text("❌ An error occurred during translation. Please try again.")

        await update.message.reply_text(
            "🌍 Please select a translation option:",
            reply_markup=ReplyKeyboardMarkup(MENU_OPTIONS, one_time_keyboard=True, resize_keyboard=True)
        )
        context.user_data["state"] = "awaiting_menu_choice"
        context.user_data.pop("source_lang", None)
        context.user_data.pop("target_lang", None)

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline queries."""
    query = update.inline_query.query.strip()
    if not query:
        return

    try:
        om_to_en = translator.translate(query, source_language="om", target_language="en")
        en_to_om = translator.translate(query, source_language="en", target_language="om")

        history = context.user_data.get("translation_history", [])
        history.extend([
            {
                "source_lang": "om",
                "target_lang": "en",
                "original_text": query,
                "translated_text": om_to_en["translatedText"],
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            },
            {
                "source_lang": "en",
                "target_lang": "om",
                "original_text": query,
                "translated_text": en_to_om["translatedText"],
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        ])
        context.user_data["translation_history"] = history[-HISTORY_LIMIT:]

        # Generate unique translation IDs
        translation_id_om = str(uuid.uuid4())
        translation_id_en = str(uuid.uuid4())
        context.user_data.setdefault("translation_records", {})[translation_id_om] = {
            "original_text": query,
            "translated_text": om_to_en["translatedText"],
            "source_lang": "om",
            "target_lang": "en"
        }
        context.user_data.setdefault("translation_records", {})[translation_id_en] = {
            "original_text": query,
            "translated_text": en_to_om["translatedText"],
            "source_lang": "en",
            "target_lang": "om"
        }

        results = [
            InlineQueryResultArticle(
                id="om_to_en",
                title="Afaan Oromo to English",
                input_message_content=InputTextMessageContent(
                    f"*Original* (Afaan Oromo): {query}\n*Translated* (English): {om_to_en['translatedText']}",
                    parse_mode="Markdown"
                ),
                description=om_to_en["translatedText"],
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("👍 Good", callback_data=f"rate_good_om_en_{translation_id_om}_0"),
                        InlineKeyboardButton("👎 Poor", callback_data=f"rate_poor_om_en_{translation_id_om}_0")
                    ]
                ])
            ),
            InlineQueryResultArticle(
                id="en_to_om",
                title="English to Afaan Oromo",
                input_message_content=InputTextMessageContent(
                    f"*Original* (English): {query}\n*Translated* (Afaan Oromo): {en_to_om['translatedText']}",
                    parse_mode="Markdown"
                ),
                description=en_to_om["translatedText"],
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("👍 Good", callback_data=f"rate_good_en_om_{translation_id_en}_0"),
                        InlineKeyboardButton("👎 Poor", callback_data=f"rate_poor_en_om_{translation_id_en}_0")
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
        parts = data.split("_")
        if len(parts) != 5:
            raise ValueError("Invalid callback_data format")
        rating, source_lang, target_lang, translation_id, _ = parts

        # Retrieve translation from context.user_data
        translations = context.user_data.get("translation_records", {})
        translation = translations.get(translation_id)
        if not translation:
            raise ValueError("Translation not found")

        original_text = translation["original_text"]
        translated_text = translation["translated_text"]

        feedback = f"User: {username} (ID: {user_id}), Rating: {rating}, Source: {source_lang}, Target: {target_lang}, Original: {original_text}, Translated: {translated_text}\n"
        try:
            with open(FEEDBACK_FILE, "a") as f:
                f.write(feedback)
        except OSError as e:
            logger.error(f"Failed to write to feedback file: {e}")

        await query.answer(f"Thank you for your {rating.replace('rate_', '')} rating!")
        await query.edit_message_text(query.message.text + f"\n\n*Rated*: {rating.replace('rate_', '')}", parse_mode="Markdown")

        # Clean up old translations
        if len(translations) > 100:  # Limit stored translations
            translations.pop(next(iter(translations)))
    except Exception as e:
        logger.error(f"Rating error: {e}, Callback data: {data}")
        await query.answer("Error processing your rating.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors caused by updates."""
    logger.error(f"Update {update} caused error {context.error}")
    if update and update.message:
        await update.message.reply_text("❌ An unexpected error occurred. Please try again.")

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

    port = int(os.getenv("PORT", 10000))
    logger.info(f"Starting webhook server on port {port}")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(InlineQueryHandler(inline_query))
    app.add_handler(CallbackQueryHandler(handle_rating, pattern=r"^rate_(good|poor)_.*"))
    app.add_error_handler(error_handler)

    web_app = web.Application()
    web_app["bot"] = app
    web_app.router.add_post("/webhook", webhook)
    web_app.router.add_route("*", "/", health_check)

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