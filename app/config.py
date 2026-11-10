import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseModel):
    PROJECT_NAME: str = "AI Moderation System"
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:////tmp/moderation.db" if os.getenv("VERCEL") else "sqlite+aiosqlite:///./moderation.db"
    )
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    QUARANTINE_THRESHOLD: int = int(os.getenv("QUARANTINE_THRESHOLD", "3"))
    AI_TIMEOUT_SECONDS: float = float(os.getenv("AI_TIMEOUT_SECONDS", "5.0"))
    CONFIDENCE_APPROVE_THRESHOLD: float = float(os.getenv("CONFIDENCE_APPROVE_THRESHOLD", "0.80"))
    CONFIDENCE_REJECT_THRESHOLD: float = float(os.getenv("CONFIDENCE_REJECT_THRESHOLD", "0.85"))
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "5"))

settings = Settings()
