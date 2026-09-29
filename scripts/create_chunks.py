"""Rebuild the PostgreSQL doc_chunks table from cleaned raw documents."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from sqlalchemy import delete, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.chunking import chunk_markdown
from src.db.models import DocChunk, RawDocument
from src.db.session import AsyncSessionLocal, engine


async def create_chunks() -> tuple[int, int]:
    try:
        async with engine.begin() as connection:
            await connection.run_sync(lambda sync_connection: DocChunk.__table__.create(sync_connection, checkfirst=True))

        async with AsyncSessionLocal() as session:
            documents = (
                await session.execute(
                    select(RawDocument.id, RawDocument.title, RawDocument.markdown_content)
                    .where(RawDocument.markdown_content.is_not(None))
                    .order_by(RawDocument.id)
                )
            ).all()
        rows: list[DocChunk] = []
        for document_id, title, markdown in documents:
            for chunk in chunk_markdown(document_id, title or "", markdown or ""):
                rows.append(
                    DocChunk(
                        document_id=chunk["document_id"],
                        chunk_index=chunk["chunk_index"],
                        content=chunk["content"],
                        token_count=chunk["token_count"],
                        metadata_json=chunk["metadata"],
                    )
                )

        async with AsyncSessionLocal() as session:
            async with session.begin():
                await session.execute(delete(DocChunk))
                session.add_all(rows)
        return len(documents), len(rows)
    finally:
        await engine.dispose()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    document_count, chunk_count = asyncio.run(create_chunks())
    print(f"Обработано документов: {document_count}")
    print(f"Создано чанков: {chunk_count}")


if __name__ == "__main__":
    main()
