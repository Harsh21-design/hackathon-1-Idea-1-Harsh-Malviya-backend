from fastapi import APIRouter
from app.models.booking import ChatRequest, ChatResponse
from app.services.gemini_agent import GeminiAgentService

router = APIRouter(prefix="/api/chat", tags=["AI Concierge Chat"])

@router.post("", response_model=ChatResponse)
async def chat_with_agent(chat_in: ChatRequest):
    """
    Direct endpoint for Web Floating Chatbot.
    Answers inquiries and books tables using Google Gemini AI.
    """
    res = await GeminiAgentService.chat(
        user_message=chat_in.message,
        history=chat_in.history,
        channel="web"
    )
    return res
