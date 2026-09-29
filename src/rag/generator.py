"""Grounded answer generation through the OpenRouter chat completions API."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openrouter/free"


SYSTEM_PROMPT = """Ты — строгий юридический ассистент проекта «Идите Лесом».
Отвечай только на основании предоставленных ниже фрагментов базы знаний. Не
добавляй юридические правила, факты или выводы, которых нет в контексте. Если контекст не содержит ответа, прямо скажи:
«В базе знаний „Идите Лесом“ нет информации, чтобы ответить на этот вопрос».

СТРОГИЕ ПРАВИЛА ОФОРМЛЕНИЯ (ТОЛЬКО БАЗОВЫЙ TELEGRAM HTML):
1. РАЗРЕШЕННЫЕ ТЕГИ:
   — Жирный текст: <b>текст</b>
   — Курсив: <i>текст</i>
   — Ссылки: <a href="URL">текст ссылки</a>
2. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНЫ теги: <ul>, <li>, <ol>, <p>, <br>, <div>.
   — Для списков используй обычные дефисы (-) или эмодзи/буллеты (•).
3. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕН Markdown: никаких звёздочек (**текст**), никаких [текст](url).
4. ЗАПРЕЩЕНЫ спецсимволы цитирования вида 【3†L1-L3】 или слитные цифры без контекста.

ПРИМЕР ПРАВИЛЬНОГО ОТВЕТА:
<b>Как стоят дела в Испании:</b>

• Для ЛГБТК+ персон из России достаточно своего статуса, чтобы подать на убежище.
• При отсутствии визы можно въехать через испанский аэропорт с пересадкой.

<b>Источники:</b>
• <a href="https://example.com">Инструкция по убежищу в Испании</a>"""

def _section_label(metadata: Any) -> str:
    if isinstance(metadata, dict):
        parts = [str(value).strip() for value in metadata.values() if value]
        return " > ".join(parts)
    if isinstance(metadata, (list, tuple)):
        return " > ".join(str(value).strip() for value in metadata if value)
    return str(metadata).strip() if metadata else ""


class RAGGenerator:
    """Generate answers grounded in retrieved chunks using OpenRouter."""

    def __init__(
        self,
        *,
        client: Any | None = None,
        model: str = DEFAULT_MODEL,
    ) -> None:
        self.model = model
        if client is None:
            project_root = Path(__file__).resolve().parents[2]
            load_dotenv(project_root / ".env")
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                raise RuntimeError("OPENROUTER_API_KEY is missing from the environment or .env")
            from openai import OpenAI

            client = OpenAI(
                base_url=OPENROUTER_BASE_URL,
                api_key=api_key,
                timeout=90,
            )
        self.client = client

    @staticmethod
    def format_context(retrieved_chunks: list[dict[str, Any]]) -> str:
        """Format chunk content and its existing source references for the model."""
        if not retrieved_chunks:
            return "Контекст не найден. Не делай выводов без источников."

        formatted: list[str] = []
        for index, chunk in enumerate(retrieved_chunks, start=1):
            title = str(chunk.get("title") or "Без названия").strip()
            section = _section_label(chunk.get("metadata"))
            header = f"### Источник {index}: {title}"
            if section:
                header += f"\nРаздел: {section}"
            chunk_id = chunk.get("chunk_id")
            if chunk_id is not None:
                header += f"\nID фрагмента: {chunk_id}"
            content = str(chunk.get("content") or "").strip()
            # Include explicit source fields when available; URLs embedded in content
            # remain unchanged and are consequently available for citation as well.
            source_url = chunk.get("source_url") or chunk.get("url")
            if source_url and str(source_url) not in content:
                content = f"{content}\nИсточник: {source_url}".strip()
            formatted.append(f"{header}\n\n{content}".rstrip())
        return "\n\n---\n\n".join(formatted)

    def generate_answer(self, query: str, retrieved_chunks: list[dict[str, Any]]) -> str:
        """Ask the configured model to answer using only the retrieved context."""
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")

        context = self.format_context(retrieved_chunks)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Вопрос пользователя:\n{query.strip()}\n\nКонтекст базы знаний:\n{context}",
                },
            ],
            temperature=0.1,
            max_tokens=1600,
        )
        try:
            answer = response.choices[0].message.content
        except (AttributeError, IndexError, TypeError) as exc:
            raise RuntimeError("OpenRouter returned an empty or invalid response") from exc
        if not isinstance(answer, str) or not answer.strip():
            raise RuntimeError("OpenRouter returned an empty answer")
        return answer.strip()

    def close(self) -> None:
        close = getattr(self.client, "close", None)
        if close is not None:
            close()
