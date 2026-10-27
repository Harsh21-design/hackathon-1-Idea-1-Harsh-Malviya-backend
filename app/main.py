import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.routers import bookings, chat

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def _start_telegram_bot():
    """
    Starts the Telegram Bot in background.
    Non-blocking: a connection timeout does NOT crash the FastAPI server.
    """
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.info("Telegram Bot: No token set, skipping.")
        return

    try:
        from telegram.ext import Application
        from app.services.telegram_bot import create_telegram_app

        tg_app = create_telegram_app()
        if not tg_app:
            return

        await asyncio.wait_for(tg_app.initialize(), timeout=20.0)
        await tg_app.start()
        # Skip deleteWebhook (pass drop_pending_updates=False, no bootstrap webhook deletion)
        await tg_app.updater.start_polling(
            drop_pending_updates=True,
            bootstrap_retries=0,   # no retries = no timeout hang
            error_callback=lambda e: logger.warning(f"Telegram polling error: {e}"),
        )
        logger.info("Telegram Bot: Polling started successfully.")
        # Keep running
        while True:
            await asyncio.sleep(3600)

    except asyncio.TimeoutError:
        logger.warning(
            "Telegram Bot: Init timed out (api.telegram.org unreachable). "
            "Bot disabled for this session. Check network/VPN."
        )
    except asyncio.CancelledError:
        logger.info("Telegram Bot: Background task cancelled cleanly.")
    except Exception as e:
        logger.warning(f"Telegram Bot startup error (non-critical): {e}")


_telegram_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _telegram_task
    _telegram_task = asyncio.create_task(_start_telegram_bot())
    logger.info("Reservas Iturrieta API ready. Telegram Bot starting in background...")

    yield  # Server is UP and handling requests

    if _telegram_task and not _telegram_task.done():
        _telegram_task.cancel()
        try:
            await _telegram_task
        except asyncio.CancelledError:
            pass
    logger.info("Shutdown complete.")


app = FastAPI(
    title="Reservas Iturrieta - Table Booking & AI Agent API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(bookings.router)
app.include_router(chat.router)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Reservas Iturrieta Backend",
        "groq_configured": bool(settings.GROQ_API_KEY),
        "gemini_configured": bool(settings.GEMINI_API_KEY),
        "telegram_configured": bool(settings.TELEGRAM_BOT_TOKEN),
        "telegram_online": _telegram_task is not None and not _telegram_task.done()
    }
