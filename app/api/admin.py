from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, or_
from typing import List, Optional
from datetime import datetime, timezone

from app.database import get_db
from app.models import Message, MessageReport, BannedUser, RegexLog, MessageStatus
from app.schemas import MessageResponse, AdminModerateRequest, AdminStatsResponse, ReportResponse
from app.services.gemini_service import moderate_and_translate_with_gemini

router = APIRouter(prefix="/api/v1/admin", tags=["Admin Panel"])

@router.get("/messages")
async def list_admin_messages(
    status_filter: Optional[str] = Query(None, alias="status"),
    has_reports: Optional[bool] = None,
    type_filter: Optional[str] = Query(None, alias="type"),
    queue: Optional[str] = Query(None, description="'attention' для очереди требующих внимания"),
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """
    Получение списка сообщений для панели модератора с фильтрацией и пагинацией.
    Поддерживает очереди:
    - queue='attention': Сообщения со статусом QUARANTINED, PENDING_MODERATION или имеющие жалобы
    """
    query = select(Message)

    if queue == "attention":
        query = query.where(
            or_(
                Message.status.in_([MessageStatus.QUARANTINED.value, MessageStatus.PENDING_MODERATION.value]),
                Message.reports_count > 0
            )
        ).order_by(desc(Message.reports_count), desc(Message.created_at))
    else:
        if status_filter:
            query = query.where(Message.status == status_filter.upper())
        if has_reports is True:
            query = query.where(Message.reports_count > 0)
        if type_filter:
            query = query.where(Message.type == type_filter.upper())
        query = query.order_by(desc(Message.created_at))

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    messages = result.scalars().all()

    # Собираем детализированные карточки включая список жалоб
    response_items = []
    for msg in messages:
        # Загружаем прикрепленные жалобы
        reports_stmt = select(MessageReport).where(MessageReport.message_id == msg.id).order_by(desc(MessageReport.created_at))
        reports_res = await db.execute(reports_stmt)
        reports = reports_res.scalars().all()

        item = {
            "id": msg.id,
            "user_id": msg.user_id,
            "user_name": msg.user_name,
            "user_ip": msg.user_ip,
            "type": msg.type,
            "original_text": msg.original_text,
            "detected_lang": msg.detected_lang,
            "text_ru": msg.text_ru,
            "text_uz": msg.text_uz,
            "status": msg.status,
            "ai_violations": msg.ai_violations or [],
            "ai_reason": msg.ai_reason,
            "ai_confidence": msg.ai_confidence,
            "reports_count": msg.reports_count,
            "verified_by_human": msg.verified_by_human,
            "created_at": msg.created_at.isoformat(),
            "updated_at": msg.updated_at.isoformat(),
            "reports": [
                {
                    "id": r.id,
                    "reason": r.reason,
                    "comment": r.comment,
                    "reporter_ip": r.reporter_ip,
                    "created_at": r.created_at.isoformat()
                }
                for r in reports
            ]
        }
        response_items.append(item)

    return response_items

@router.patch("/messages/{message_id}/moderate")
async def moderate_message(
    message_id: str,
    payload: AdminModerateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Принятие решения модератором:
    - APPROVE: Одобрить и опубликовать (verified_by_human = True, reports_count = 0)
    - REJECT: Заблокировать (REJECTED_BY_ADMIN)
    - ban_user: Забанить автора сообщения
    """
    stmt = select(Message).where(Message.id == message_id)
    result = await db.execute(stmt)
    msg = result.scalars().first()

    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сообщение не найдено")

    action = payload.action.upper()
    if action == "APPROVE":
        msg.status = MessageStatus.PUBLISHED.value
        msg.reports_count = 0
        msg.verified_by_human = True
    elif action == "REJECT":
        msg.status = MessageStatus.REJECTED_BY_ADMIN.value
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Недопустимое действие. Используйте APPROVE или REJECT")

    msg.updated_at = datetime.now(timezone.utc)

    # Бан пользователя
    if payload.ban_user:
        ban_entry = BannedUser(
            user_id=msg.user_id,
            user_ip=msg.user_ip,
            reason=f"Заблокирован администратором за нарушение в сообщении #{msg.id}"
        )
        db.add(ban_entry)

    await db.commit()
    await db.refresh(msg)

    return {
        "success": True,
        "message_id": msg.id,
        "new_status": msg.status,
        "verified_by_human": msg.verified_by_human,
        "banned": payload.ban_user
    }

@router.post("/messages/{message_id}/retranslate")
async def retranslate_message(
    message_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Принудительный повторный запрос к Gemini API
    для перевода и анализа сообщения (если первичный запрос завершился таймаутом).
    """
    stmt = select(Message).where(Message.id == message_id)
    result = await db.execute(stmt)
    msg = result.scalars().first()

    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сообщение не найдено")

    ai_result = await moderate_and_translate_with_gemini(msg.original_text)
    if not ai_result:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Не удалось получить ответ от Gemini API")

    msg.detected_lang = ai_result.detected_language
    msg.text_ru = ai_result.translations.ru
    msg.text_uz = ai_result.translations.uz
    msg.ai_violations = ai_result.violation_categories
    msg.ai_reason = ai_result.reason_ru
    msg.ai_confidence = ai_result.confidence_score
    msg.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(msg)

    return {
        "success": True,
        "message_id": msg.id,
        "detected_lang": msg.detected_lang,
        "text_ru": msg.text_ru,
        "text_uz": msg.text_uz,
        "ai_reason": msg.ai_reason,
        "ai_confidence": msg.ai_confidence
    }

@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(db: AsyncSession = Depends(get_db)):
    """
    Сводная статистика по всем сообщениям, статусам модерации и жалобам.
    """
    async def count_status(s: str) -> int:
        res = await db.execute(select(func.count(Message.id)).where(Message.status == s))
        return res.scalar() or 0

    published = await count_status(MessageStatus.PUBLISHED.value)
    pending = await count_status(MessageStatus.PENDING_MODERATION.value)
    quarantined = await count_status(MessageStatus.QUARANTINED.value)
    rejected_ai = await count_status(MessageStatus.REJECTED_BY_AI.value)
    rejected_admin = await count_status(MessageStatus.REJECTED_BY_ADMIN.value)

    regex_res = await db.execute(select(func.count(RegexLog.id)))
    regex_blocked = regex_res.scalar() or 0

    total_msg_res = await db.execute(select(func.count(Message.id)))
    total_messages = total_msg_res.scalar() or 0

    reports_res = await db.execute(select(func.count(MessageReport.id)))
    total_reports = reports_res.scalar() or 0

    return AdminStatsResponse(
        published_count=published,
        pending_count=pending,
        quarantined_count=quarantined,
        rejected_ai_count=rejected_ai,
        rejected_admin_count=rejected_admin,
        regex_blocked_count=regex_blocked,
        total_messages=total_messages,
        total_reports=total_reports
    )

@router.get("/regex-logs")
async def get_regex_logs(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """
    Лог попыток отправки сообщений, заблокированных на этапе RegEx.
    """
    stmt = select(RegexLog).order_by(desc(RegexLog.created_at)).limit(limit)
    res = await db.execute(stmt)
    logs = res.scalars().all()
    return logs
