from types import SimpleNamespace

import pytest

from rag.generator import DEFAULT_MODEL, RAGGenerator, SYSTEM_PROMPT


class FakeCompletions:
    def __init__(self, content: str = "Ответ со ссылкой [источник](https://example.org)"):
        self.content = content
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


def fake_client(content: str = "Ответ со ссылкой [источник](https://example.org)"):
    completions = FakeCompletions(content)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return client, completions


def test_format_context_keeps_titles_sections_and_source_links():
    context = RAGGenerator.format_context(
        [
            {
                "title": "Отсрочка от мобилизации",
                "chunk_id": 42,
                "metadata": {"h2": "Основания", "h3": "Учеба"},
                "content": "Подробности в [законе](https://example.org/law).",
            }
        ]
    )

    assert "Отсрочка от мобилизации" in context
    assert "Основания > Учеба" in context
    assert "ID фрагмента: 42" in context
    assert "https://example.org/law" in context


def test_generate_answer_sends_grounded_prompt_and_returns_text():
    client, completions = fake_client("Краткий ответ.")
    generator = RAGGenerator(client=client)
    chunks = [{"title": "Закон", "content": "Источник: https://example.org/law", "metadata": {"h2": "Норма"}}]

    answer = generator.generate_answer("Что сказано в законе?", chunks)

    assert answer == "Краткий ответ."
    assert completions.kwargs["model"] == DEFAULT_MODEL
    messages = completions.kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert "только на основании" in SYSTEM_PROMPT
    assert messages[1]["role"] == "user"
    assert "Что сказано в законе?" in messages[1]["content"]
    assert "https://example.org/law" in messages[1]["content"]


def test_empty_context_is_explicitly_marked():
    assert "Контекст не найден" in RAGGenerator.format_context([])


def test_rejects_blank_query():
    client, _ = fake_client()
    with pytest.raises(ValueError, match="non-empty"):
        RAGGenerator(client=client).generate_answer("  ", [])
