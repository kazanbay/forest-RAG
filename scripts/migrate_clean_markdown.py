"""One-time migration to clean stored Markdown and refresh its content hash."""

from __future__ import annotations

import asyncio
import hashlib
import sys
from pathlib import Path

from sqlalchemy import select

# When invoked as ``python scripts/migrate_clean_markdown.py``, Python places
# scripts/ rather than the repository root on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.cleaner import clean_markdown_for_rag
from src.db.models import RawDocument
from src.db.session import AsyncSessionLocal, engine


def _content_hash(content: str | None) -> str | None:
    """Match the scraper's existing MD5/32-character content_hash format."""
    if content is None:
        return None
    return hashlib.md5(content.encode("utf-8")).hexdigest()


async def migrate() -> int:
    updated = 0
    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                documents = (await session.scalars(select(RawDocument))).all()
                for document in documents:
                    original = document.markdown_content
                    cleaned = clean_markdown_for_rag(original) if original is not None else None
                    content_hash = _content_hash(cleaned)
                    if original != cleaned or document.content_hash != content_hash:
                        document.markdown_content = cleaned
                        document.content_hash = content_hash
                        updated += 1
        return updated
    finally:
        await engine.dispose()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    count = asyncio.run(migrate())
    print(f"Миграция завершена. Обновлено строк: {count}")


if __name__ == "__main__":
    main()
