"""Report BAAI/bge-m3 token lengths for documents in raw_documents."""

from __future__ import annotations

import asyncio
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.db.models import RawDocument
from src.db.session import AsyncSessionLocal, engine


MODEL_NAME = "BAAI/bge-m3"
LIMITS = (512, 1024, 2048, 8192)


@dataclass(frozen=True)
class DocumentLength:
    document_id: int
    title: str
    characters: int
    tokens: int


async def load_documents() -> list[tuple[int, str | None, str | None]]:
    try:
        async with AsyncSessionLocal() as session:
            rows = await session.execute(
                select(RawDocument.id, RawDocument.title, RawDocument.markdown_content)
            )
            return list(rows.all())
    finally:
        await engine.dispose()


def analyze_documents(documents: list[tuple[int, str | None, str | None]], tokenizer) -> list[DocumentLength]:
    results = []
    for document_id, title, markdown in documents:
        title = title or ""
        content = markdown or ""
        text = f"{title}\n\n{content}"
        token_ids = tokenizer(text, add_special_tokens=False, truncation=False)["input_ids"]
        results.append(DocumentLength(document_id, title, len(text), len(token_ids)))
    return results


def _shorten(value: str, width: int = 64) -> str:
    value = " ".join(value.split())
    if len(value) > width:
        return value[: width - 1] + "…"
    return value


def print_report(results: list[DocumentLength]) -> None:
    print(f"Токенизатор: {MODEL_NAME}")
    print(f"Документов: {len(results)}")
    print("\nТоп-10 самых длинных документов (по числу токенов):")
    print(f"{'ID':>8}  {'Заголовок':<64}  {'Символов':>10}  {'Токенов bge-m3':>14}")
    print("-" * 104)
    for item in sorted(results, key=lambda row: (-row.tokens, row.document_id))[:10]:
        print(
            f"{item.document_id:>8}  {_shorten(item.title):<64}  "
            f"{item.characters:>10}  {item.tokens:>14}"
        )

    if not results:
        print("\nОбщая статистика: база не содержит документов.")
        return

    counts = [item.tokens for item in results]
    print("\nОбщая статистика токенов:")
    print(f"Минимум: {min(counts)}")
    print(f"Среднее: {statistics.mean(counts):.2f}")
    print(f"Медиана: {statistics.median(counts):.2f}")
    print(f"Максимум: {max(counts)}")

    print("\nРаспределение по лимитам (включительно):")
    for limit in LIMITS:
        count = sum(token_count <= limit for token_count in counts)
        percentage = count / len(counts) * 100
        print(f"≤ {limit:>4} токенов: {count:>6} ({percentage:5.1f}%)")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from transformers import AutoTokenizer

    print(f"Загружаю токенизатор {MODEL_NAME}…", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    documents = asyncio.run(load_documents())
    print_report(analyze_documents(documents, tokenizer))


if __name__ == "__main__":
    main()
