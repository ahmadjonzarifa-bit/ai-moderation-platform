import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean, DateTime, JSON, ForeignKey, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
import enum
from app.database import Base

def get_utc_now():
    return datetime.now(timezone.utc)

class MessageType(str, enum.Enum):
    REVIEW = "REVIEW"
    COMMENT = "COMMENT"
    TICKET = "TICKET"

class MessageStatus(str, enum.Enum):
    PENDING_MODERATION = "PENDING_MODERATION"
    PUBLISHED = "PUBLISHED"
    REJECTED_BY_REGEX = "REJECTED_BY_REGEX"
    REJECTED_BY_AI = "REJECTED_BY_AI"
    QUARANTINED = "QUARANTINED"
    REJECTED_BY_ADMIN = "REJECTED_BY_ADMIN"

class ReportReason(str, enum.Enum):
    SPAM = "SPAM"
    INSULT = "INSULT"
    LINKS = "LINKS"
    CTA = "CTA"
    OTHER = "OTHER"

def generate_uuid() -> str:
    return str(uuid.uuid4())

class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(64), nullable=False, index=True)
    user_name = Column(String(100), nullable=False, default="Аноним")
    user_ip = Column(String(45), nullable=True)
    type = Column(String(20), nullable=False, default=MessageType.COMMENT.value)
    original_text = Column(Text, nullable=False)
    detected_lang = Column(String(10), nullable=True)
    text_ru = Column(Text, nullable=True)
    text_uz = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default=MessageStatus.PENDING_MODERATION.value, index=True)
    ai_violations = Column(JSON, nullable=True, default=list)
    ai_reason = Column(Text, nullable=True)
    ai_confidence = Column(Float, nullable=True)
    reports_count = Column(Integer, default=0, nullable=False)
    verified_by_human = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=get_utc_now, nullable=False)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now, nullable=False)

    reports = relationship("MessageReport", back_populates="message", cascade="all, delete-orphan")

class MessageReport(Base):
    __tablename__ = "message_reports"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    message_id = Column(String(36), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)
    reporter_id = Column(String(64), nullable=True, index=True)
    reporter_ip = Column(String(45), nullable=False, index=True)
    reason = Column(String(20), nullable=False, default=ReportReason.SPAM.value)
    comment = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=get_utc_now, nullable=False)

    message = relationship("Message", back_populates="reports")

class BannedUser(Base):
    __tablename__ = "banned_users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(64), nullable=True, index=True)
    user_ip = Column(String(45), nullable=True, index=True)
    reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=get_utc_now, nullable=False)

class RegexLog(Base):
    __tablename__ = "regex_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(64), nullable=True)
    user_ip = Column(String(45), nullable=True)
    original_text = Column(Text, nullable=False)
    violation_reason = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=get_utc_now, nullable=False)
