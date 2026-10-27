import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from app.core.config import settings
from app.services.groq_agent import GroqAgentService
from app.services.gemini_agent import GeminiAgentService
from app.models.booking import ChatMessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

chat_histories: dict[int, list[ChatMessage]] = {}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name if update.effective_user else "Guest"
    welcome_text = (
        f"Kaixo {user_name}! 🍎 Welcome to Reservas Iturrieta (Aramaio, Est. 1998).\n\n"
        "I can help you:\n"
        "• Explore our traditional Basque txotx cider menu.\n"
        "• Check live table availability and instantly book your table!\n\n"
        "When would you like to visit and for how many guests?"
    )
    await update.message.reply_text(welcome_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_text = update.message.text

    history = chat_histories.get(chat_id, [])
    
    if settings.GROQ_API_KEY:
        res = await GroqAgentService.chat(user_message=user_text, history=history, channel="telegram")
    else:
        res = await GeminiAgentService.chat(user_message=user_text, history=history, channel="telegram")
    
    history.append(ChatMessage(role="user", content=user_text))
    history.append(ChatMessage(role="model", content=res.reply))
    chat_histories[chat_id] = history[-10:]

    await update.message.reply_text(res.reply)

def create_telegram_app():
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN is not set in backend .env. Bot listener will stay inactive.")
        return None

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app
