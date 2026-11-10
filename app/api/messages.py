from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List

from app.database import get_db
from app.models import Message, MessageStatus
from app.schemas import MessageCreate, MessageResponse, ReportCreate, RegexCheckResponse
from app.services.moderation import process_new_message, add_message_report
from app.filters.regex_filter import check_text_regex

router = APIRouter(prefix="/api/v1/messages", tags=["Messages (Public)"])

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"

@router.post("", response_model=MessageResponse)
async def create_message(
    message_in: MessageCreate,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """
    Отправка нового отзыва/комментария/заявки.
    Процесс: RegEx фильтр -> Gemini AI (модерация + перевод) -> сохранение.
    Коды ответа:
    - 201: Опубликовано
    - 202: Отправлено на ручную модерацию
    - 422: Отклонено RegEx или AI (с детальным объяснением)
    - 403: Пользователь или IP заблокирован
    """
    client_ip = get_client_ip(request)
    msg, status_code, explanation = await process_new_message(db, message_in, client_ip)

    if status_code == 403:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=explanation)

    if status_code == 422:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": explanation,
                "status": msg.status if msg else "REJECTED_BY_REGEX",
                "ai_reason": msg.ai_reason if msg else explanation,
                "ai_violations": msg.ai_violations if msg else ["REGEX_RULE"]
            }
        )

    response.status_code = status_code
    return msg

@router.get("", response_model=List[MessageResponse])
async def list_published_messages(
    type: str = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """
    Публичная лента одобренных сообщений (PUBLISHED).
    Сообщения в статусе QUARANTINED автоматически скрываются.
    """
    query = select(Message).where(Message.status == MessageStatus.PUBLISHED.value)
    if type:
        query = query.where(Message.type == type.upper())
    query = query.order_by(desc(Message.created_at)).offset(offset).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()

@router.post("/{message_id}/report")
async def report_message(
    message_id: str,
    report_in: ReportCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Подача жалобы на сообщение пользователем.
    При превышении порога жалоб сообщение скрывается на модерацию (QUARANTINED).
    """
    client_ip = get_client_ip(request)
    success, message_text, msg = await add_message_report(db, message_id, report_in, client_ip)

    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message_text)

    return {
        "success": True,
        "detail": message_text,
        "message_id": message_id,
        "current_status": msg.status,
        "reports_count": msg.reports_count
    }

@router.post("/check-regex", response_model=RegexCheckResponse)
async def check_regex_live(payload: dict):
    """
    Быстрый онлайн pre-check текста без обращения к базе данных и AI.
    Используется фронтендом в реальном времени при вводе сообщения.
    """
    text = payload.get("text", "")
    is_valid, reason, violation_type, _ = check_text_regex(text)
    return RegexCheckResponse(
        is_valid=is_valid,
        reason=reason,
        violation_type=violation_type
    )
