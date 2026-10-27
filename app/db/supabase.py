from supabase import create_client, Client
from app.core.config import settings

def get_supabase_client() -> Client:
    # Prefer service role key if available for administrative / agent writes
    key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_KEY
    if not settings.SUPABASE_URL or not key:
        raise ValueError("Supabase URL and Key must be set in backend .env")
    return create_client(settings.SUPABASE_URL, key)
