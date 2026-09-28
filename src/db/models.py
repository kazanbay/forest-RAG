from datetime import datetime
from typing import Optional, Any
from sqlalchemy import Boolean, Integer, String, Text, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column
from src.db.session import Base

class RawDocument(Base):
    __tablename__ = "raw_documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # URL may appear in multiple rows so older versions can remain as soft-deleted history.
    url: Mapped[str] = mapped_column(String(2048), index=True, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    html_content: Mapped[str] = mapped_column(Text, nullable=False)
    markdown_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    last_parsed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

class FeedbackLog(Base):
    __tablename__ = "feedback_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_query: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_chunks: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    rag_raw_response: Mapped[str] = mapped_column(Text, nullable=False)
    final_human_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rating: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
