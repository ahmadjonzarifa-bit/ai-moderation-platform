import logging
import uuid
from typing import Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.config import settings
from app.models import Message, MessageReport, BannedUser, RegexLog, MessageStatus
from app.schemas import MessageCreate, ReportCreate, GeminiModerationResponse
from app.filters.regex_filter import check_text_regex
from app.services.gemini_service import moderate_and_translate_with_gemini

logger = logging.getLogger(__name__)

async def is_user_banned(db: AsyncSession, user_id: Optional[str], user_ip: Optional[str]) -> bool:
    """Проверяет, заблокирован ли пользователь по user_id или IP."""
    conditions = []
    if user_id:
        conditions.append(BannedUser.user_id == user_id)
    if user_ip:
        conditions.append(BannedUser.user_ip == user_ip)

    if not conditions:
        return False

    from sqlalchemy import or_
    stmt = select(BannedUser).where(or_(*conditions))
    result = await db.execute(stmt)
    return result.scalars().first() is not None

async def process_new_message(
    db: AsyncSession,
    message_in: MessageCreate,
    client_ip: Optional[str]
) -> Tuple[Optional[Message], int, str]:
    """
    Основной воркфлоу обработки входящего сообщения:
    1. Проверка на бан пользователя/IP
    2. RegEx фильтрация (Level 1)
    3. AI Модерация и двуязычный перевод через Gemini (Level 2)
    4. Сохранение в БД с нужным статусом
    Возвращает (Message, http_status_code, explanation_message)
    """
    user_id = message_in.user_id or str(uuid.uuid4())
    user_name = message_in.user_name or "Аноним"
    original_text = message_in.original_text.strip()

    # 0. Проверка бана
    if await is_user_banned(db, user_id, client_ip):
        return None, 403, "Доступ ограничен. Ваш аккаунт или IP-адрес заблокирован за нарушение правил."

    # 1. Этап 1: Pre-check (RegEx на бэкенде)
    is_valid_regex, regex_reason, violation_type, matched_snippet = check_text_regex(original_text)
    if not is_valid_regex:
        # Логируем попытку нарушения в regex_logs
        log_entry = RegexLog(
            user_id=user_id,
            user_ip=client_ip,
            original_text=original_text,
            violation_reason=f"[{violation_type}] {regex_reason} (совпадение: '{matched_snippet}')"
        )
        db.add(log_entry)
        await db.commit()

        # Возвращаем 422 Unprocessable Entity
        return None, 422, f"Отклонено фильтром безопасности: {regex_reason}"

    # 2. Этап 2: AI-Модерация и перевод (Gemini API)
    ai_result: Optional[GeminiModerationResponse] = await moderate_and_translate_with_gemini(original_text)

    if ai_result is None:
        # Gemini API недоступен, таймаут или ключ не задан -> PENDING_MODERATION
        new_msg = Message(
            user_id=user_id,
            user_name=user_name,
            user_ip=client_ip,
            type=message_in.type.upper(),
            original_text=original_text,
            detected_lang="unknown",
            text_ru=original_text,
            text_uz=original_text,
            status=MessageStatus.PENDING_MODERATION.value,
            ai_violations=[],
            ai_reason="AI-сервис временно недоступен или ожидает ручной проверки",
            ai_confidence=0.0,
            reports_count=0,
            verified_by_human=False
        )
        db.add(new_msg)
        await db.commit()
        await db.refresh(new_msg)
        return new_msg, 202, "Сообщение отправлено на ручную модерацию."

    # Анализ решения AI
    confidence = ai_result.confidence_score
    is_approved = ai_result.is_approved
    violations = ai_result.violation_categories
    reason_ru = ai_result.reason_ru
    detected_lang = ai_result.detected_language
    text_ru = ai_result.translations.ru
    text_uz = ai_result.translations.uz

    if is_approved and confidence >= settings.CONFIDENCE_APPROVE_THRESHOLD:
        status = MessageStatus.PUBLISHED.value
        http_code = 201
        msg_note = "Сообщение успешно проверено AI и опубликовано."
    elif not is_approved and confidence >= settings.CONFIDENCE_REJECT_THRESHOLD:
        status = MessageStatus.REJECTED_BY_AI.value
        http_code = 422
        msg_note = reason_ru or "Сообщение отклонено AI-модератором за нарушение правил платформы."
    else:
        # Сомнительный случай (confidence < 0.8)
        status = MessageStatus.PENDING_MODERATION.value
        http_code = 202
        msg_note = "Сообщение передано на дополнительную ручную проверку модератором."

    new_msg = Message(
        user_id=user_id,
        user_name=user_name,
        user_ip=client_ip,
        type=message_in.type.upper(),
        original_text=original_text,
        detected_lang=detected_lang,
        text_ru=text_ru,
        text_uz=text_uz,
        status=status,
        ai_violations=violations,
        ai_reason=reason_ru,
        ai_confidence=confidence,
        reports_count=0,
        verified_by_human=False
    )
    db.add(new_msg)
    await db.commit()
    await db.refresh(new_msg)

    return new_msg, http_code, msg_note

async def add_message_report(
    db: AsyncSession,
    message_id: str,
    report_in: ReportCreate,
    client_ip: str
) -> Tuple[bool, str, Optional[Message]]:
    """
    Обрабатывает жалобу на опубликованное сообщение (Этап 3: Пост-модерация).
    - Защита от дублей по IP / reporter_id
    - Авто-карантин при достижении N жалоб
    """
    stmt = select(Message).where(Message.id == message_id)
    result = await db.execute(stmt)
    msg = result.scalars().first()

    if not msg:
        return False, "Сообщение не найдено", None

    # Защита от повторных жалоб от одного и того же пользователя / IP
    from sqlalchemy import or_, and_
    conditions = [MessageReport.message_id == message_id]
    user_cond = []
    if report_in.reporter_id:
        user_cond.append(MessageReport.reporter_id == report_in.reporter_id)
    if client_ip:
        user_cond.append(MessageReport.reporter_ip == client_ip)

    if user_cond:
        existing_report_stmt = select(MessageReport).where(and_(*conditions, or_(*user_cond)))
        existing_result = await db.execute(existing_report_stmt)
        if existing_result.scalars().first():
            return False, "Вы уже отправляли жалобу на данное сообщение", msg

    # Создание записи жалобы
    report = MessageReport(
        message_id=message_id,
        reporter_id=report_in.reporter_id,
        reporter_ip=client_ip,
        reason=report_in.reason.upper(),
        comment=report_in.comment
    )
    db.add(report)

    # Увеличение счетчика жалоб
    msg.reports_count += 1

    # Проверка порога авто-карантина
    # Если набрано N жалоб и сообщение ранее не было вручную проверено человеком
    if msg.reports_count >= settings.QUARANTINE_THRESHOLD and not msg.verified_by_human:
        msg.status = MessageStatus.QUARANTINED.value

    await db.commit()
    await db.refresh(msg)

    return True, "Жалоба принята. Спасибо за бдительность!", msg
