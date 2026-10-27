# Reservas Iturrieta · Autonomous Table Management & AI Backend

FastAPI-powered backend engine for **Sidrería Iturrieta (Aramaio, Álava · Est. 1998)**.

## Features
- **Smart Availability Engine**: Real-time table allocation, schedule & closure checks, instant confirmation.
- **Google Gemini 3.8 Flash**: AI hospitality agent with function calling (ook_table_tool).
- **Telegram Bot Integration**: Multi-channel conversational bookings synced in real-time.
- **Supabase Integration**: PostgreSQL table and reservations persistence.

---

## Getting Started

### 1. Prerequisites
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager:
  `powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  `

### 2. Environment Setup
Copy the example template:
`ash
cp .env.example .env
`
Fill in your keys in .env:
- SUPABASE_URL & SUPABASE_KEY
- GEMINI_API_KEY (from Google AI Studio)
- TELEGRAM_BOT_TOKEN (from @BotFather)

### 3. Run Locally
`ash
uv run uvicorn app.main:app --reload --port 8000
`
- API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health Check: [http://localhost:8000/health](http://localhost:8000/health)
