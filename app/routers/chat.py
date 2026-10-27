from fastapi import APIRouter
from app.models.booking import ChatRequest, ChatResponse
from app.services.groq_agent import GroqAgentService
from app.services.gemini_agent import GeminiAgentService
from app.core.config import settings

router = APIRouter(prefix="/api/chat", tags=["AI Concierge Chat"])

@router.post("", response_model=ChatResponse)
async def chat_with_agent(chat_in: ChatRequest):
    """
    Direct endpoint for Web Floating Chatbot.
    Prefers Groq (Ultra-fast Llama-3.3-70b) if GROQ_API_KEY is present,
    otherwise falls back to Gemini.
    """
    if settings.GROQ_API_KEY:
        res = await GroqAgentService.chat(
            user_message=chat_in.message,
            history=chat_in.history,
            channel="web"
        )
        return res

    res = await GeminiAgentService.chat(
        user_message=chat_in.message,
        history=chat_in.history,
        channel="web"
    )
    return res
