import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

class Article(Base):
    __tablename__ = "articles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String, nullable=False, default="processing")
    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    intro_hook: Mapped[str | None] = mapped_column(Text)
    intro_hook_source_quote: Mapped[str | None] = mapped_column(Text)
    body_sections: Mapped[list | None] = mapped_column(JSONB)
    best_for: Mapped[list | None] = mapped_column(JSONB)
    not_for: Mapped[list | None] = mapped_column(JSONB)
    ethics_safety_notes: Mapped[str | None] = mapped_column(Text)
    ethics_safety_notes_source_quote: Mapped[str | None] = mapped_column(Text)
    key_facts: Mapped[list | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
