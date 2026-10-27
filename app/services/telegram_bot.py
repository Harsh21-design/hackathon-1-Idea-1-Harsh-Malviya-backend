import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from app.core.config import settings
from app.models.booking import ChatMessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Per-chat conversation history store
chat_histories: dict[int, list[ChatMessage]] = {}


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name if update.effective_user else "Guest"
    welcome_text = (
        f"Welcome, {user_name}! I'm the Reservas Iturrieta booking assistant.\n\n"
        "I can help you:\n"
        "- Check table availability and book instantly\n"
        "- Explore our traditional Basque cider house menu\n\n"
        "Pricing:\n"
        "- Adults: 45 EUR per person (full menu + unlimited cider)\n"
        "- Children under 12: 22 EUR per person\n\n"
        "When would you like to visit and for how many guests?"
    )
    await update.message.reply_text(welcome_text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "Reservas Iturrieta - Bot Commands:\n\n"
        "/start - Start a new conversation\n"
        "/help - Show this help message\n"
        "/menu - View our menu & pricing\n"
        "/hours - Opening hours\n"
        "/book - Start a table reservation\n\n"
        "Or just type naturally -- I understand plain language!"
    )
    await update.message.reply_text(help_text)


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    menu_text = (
        "Traditional Basque Cider House Menu:\n\n"
        "Starters:\n"
        "- Codfish omelette\n"
        "- Fried codfish with peppers\n\n"
        "Main:\n"
        "- Charcoal-grilled Txuleta ribeye steak\n\n"
        "Cheese:\n"
        "- Idiazabal cheese with walnuts\n\n"
        "Drinks:\n"
        "- Unlimited natural cider from the barrel\n\n"
        "PRICE: Adults 45 EUR | Children under 12: 22 EUR"
    )
    await update.message.reply_text(menu_text)


async def hours_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Opening Hours:\n\n"
        "Friday, Saturday, Sunday -- Lunch service only\n"
        "Service: 13:00 to 16:00 (last seating 15:30)\n\n"
        "Closed Monday to Thursday and all evenings."
    )


async def book_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Let's get you a table! I'll need a few details:\n\n"
        "1. Your full name\n"
        "2. Phone number (with country code)\n"
        "3. Preferred date (e.g. 2026-11-01)\n"
        "4. Preferred time (13:00 to 15:30)\n"
        "5. Number of adults\n"
        "6. Number of children under 12\n\n"
        "What's your name?"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_text = update.message.text

    # Show typing indicator
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    history = chat_histories.get(chat_id, [])

    try:
        from app.core.config import settings
        from app.services.groq_agent import GroqAgentService
        from app.services.gemini_agent import GeminiAgentService

        if settings.GROQ_API_KEY:
            res = await GroqAgentService.chat(user_message=user_text, history=history, channel="telegram")
        else:
            res = await GeminiAgentService.chat(user_message=user_text, history=history, channel="telegram")

        history.append(ChatMessage(role="user", content=user_text))
        history.append(ChatMessage(role="model", content=res.reply))
        # Keep last 20 messages for context
        chat_histories[chat_id] = history[-20:]

        await update.message.reply_text(res.reply)

    except Exception as e:
        logger.error(f"Error handling message from chat {chat_id}: {e}")
        await update.message.reply_text(
            "I encountered a temporary issue. Please try again in a moment.\n"
            "You can also use our website to book a table directly."
        )


def create_telegram_app():
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN is not set. Bot listener will stay inactive.")
        return None

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("hours", hours_command))
    app.add_handler(CommandHandler("book", book_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app
