from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime

class MessageCreate(BaseModel):
    original_text: str = Field(..., min_length=2, max_length=5000, description="Текст сообщения")
    type: str = Field(default="COMMENT", description="REVIEW, COMMENT, TICKET")
    user_id: Optional[str] = Field(default=None, description="ID пользователя")
    user_name: Optional[str] = Field(default="Аноним", description="Имя пользователя")

class MessageResponse(BaseModel):
    id: str
    user_id: str
    user_name: str
    user_ip: Optional[str] = None
    type: str
    original_text: str
    detected_lang: Optional[str] = None
    text_ru: Optional[str] = None
    text_uz: Optional[str] = None
    status: str
    ai_violations: Optional[List[str]] = []
    ai_reason: Optional[str] = None
    ai_confidence: Optional[float] = None
    reports_count: int
    verified_by_human: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ReportCreate(BaseModel):
    reason: str = Field(..., description="SPAM, INSULT, LINKS, CTA, OTHER")
    comment: Optional[str] = Field(default=None, max_length=200, description="Дополнительный комментарий")
    reporter_id: Optional[str] = Field(default=None, description="ID пользователя")

class ReportResponse(BaseModel):
    id: str
    message_id: str
    reporter_id: Optional[str] = None
    reason: str
    comment: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class AdminModerateRequest(BaseModel):
    action: str = Field(..., description="APPROVE | REJECT")
    ban_user: bool = Field(default=False, description="Заблокировать ли автора сообщения")

class AdminStatsResponse(BaseModel):
    published_count: int
    pending_count: int
    quarantined_count: int
    rejected_ai_count: int
    rejected_admin_count: int
    regex_blocked_count: int
    total_messages: int
    total_reports: int

class RegexCheckResponse(BaseModel):
    is_valid: bool
    reason: Optional[str] = None
    violation_type: Optional[str] = None

class GeminiTranslations(BaseModel):
    ru: str
    uz: str

class GeminiModerationResponse(BaseModel):
    is_approved: bool
    violation_categories: List[str] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=1.0)
    reason_ru: str
    detected_language: str
    translations: GeminiTranslations
