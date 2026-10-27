import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.routers import bookings, chat
from app.services.telegram_bot import create_telegram_app

@asynccontextmanager
async def lifespan(app: FastAPI):
    tg_app = create_telegram_app()
    if tg_app:
        await tg_app.initialize()
        await tg_app.start()
        await tg_app.updater.start_polling()
        print("[Telegram Bot] Polling started successfully.")

    yield

    if tg_app and tg_app.updater:
        await tg_app.updater.stop()
        await tg_app.stop()
        await tg_app.shutdown()
        print("[Telegram Bot] Stopped cleanly.")

app = FastAPI(
    title="Reservas Iturrieta Table Booking & Concierge API",
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
        "gemini_configured": bool(settings.GEMINI_API_KEY),
        "telegram_configured": bool(settings.TELEGRAM_BOT_TOKEN)
    }
