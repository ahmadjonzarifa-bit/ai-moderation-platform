import time
from collections import defaultdict
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os

from app.config import settings
from app.database import init_db
from app.api.messages import router as messages_router
from app.api.admin import router as admin_router

# In-memory sliding window Rate Limiter
request_counts = defaultdict(list)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Инициализация таблиц базы данных при старте
    await init_db()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Система двухуровневой AI-модерации отзывов, комментариев и заявок с переводом на RU/UZ и системой жалоб",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate Limiting Middleware для отправки сообщений
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.method == "POST" and request.url.path == "/api/v1/messages":
        client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "127.0.0.1")
        now = time.time()
        # Очищаем запросы старше 60 секунд
        request_counts[client_ip] = [t for t in request_counts[client_ip] if now - t < 60]

        if len(request_counts[client_ip]) >= settings.RATE_LIMIT_PER_MINUTE:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Слишком много запросов. Лимит: не более 5 сообщений в минуту с одного адреса."}
            )

        request_counts[client_ip].append(now)

    response = await call_next(request)
    return response

# Подключение API роутеров
app.include_router(messages_router)
app.include_router(admin_router)

# Статические файлы
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", include_in_schema=False)
async def serve_index():
    index_path = os.path.join(static_dir, "index.html")
    return FileResponse(index_path)

@app.get("/admin", include_in_schema=False)
async def serve_admin():
    admin_path = os.path.join(static_dir, "admin.html")
    return FileResponse(admin_path)

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "gemini_model": settings.GEMINI_MODEL,
        "quarantine_threshold": settings.QUARANTINE_THRESHOLD
    }
