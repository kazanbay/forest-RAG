import pytest

from cleaner import clean_markdown_for_rag


def test_removes_noise_keeps_document_structure():
    raw = """# Документ

![icon](data:image/gif;base64,AAAA)
![emoji](https://notion-emojis.s3-us-west-2.amazonaws.com/abc.gif)

> Содержание
> [Раздел](https://example.org/page#abcdef1234567890)

### Раздел
Ссылка [закон](https://consultant.ru/law?pvs=25)

| Категория | Срок |
| --- | --- |
| А | 10 лет |

Мы будем рады, если вы поддержите проект: [PayPal](https://paypal.me/example)
BTC: bc1qsecret
"""
    cleaned = clean_markdown_for_rag(raw)
    assert "# Документ" in cleaned
    assert "### Раздел" in cleaned
    assert "| Категория | Срок |" in cleaned
    assert "[закон](https://consultant.ru/law)" in cleaned
    assert "data:image" not in cleaned
    assert "notion-emojis" not in cleaned
    assert "Содержание" not in cleaned
    assert "#abcdef" not in cleaned
    assert "paypal.me" not in cleaned
    assert "bc1qsecret" not in cleaned


def test_preserves_information_callout_and_unwraps_preview():
    raw = "> Примечание: закон изменился.\n\n[![preview](https://example.org/image.jpg)Читайте закон](https://example.org/law?pvs=74)"
    assert clean_markdown_for_rag(raw) == "> Примечание: закон изменился.\n\nЧитайте закон"


def test_removes_pdf_download_line_and_collapses_blank_lines():
    raw = "A\n\n\nСкачать страницу в формате PDF: [файл](https://x.test/a.pdf)\n\nB"
    assert clean_markdown_for_rag(raw) == "A\n\nB"


def test_requires_string():
    with pytest.raises(TypeError):
        clean_markdown_for_rag(None)


@pytest.mark.parametrize(
    "raw",
    [
        "This page couldn’t be found.\nSkip to content\nNotion uses cookies",
        "You may not have access to this page.\nSkip to content\nNotion uses cookies",
    ],
)
def test_discards_notion_error_pages(raw):
    assert clean_markdown_for_rag(raw) == ""


def test_cleans_inline_notion_brand_prefix_and_zero_width_characters():
    raw = "Идите лесомFAQ: ответы\nИдите лесомВыпустят ли меня на границе?\u200b"
    assert clean_markdown_for_rag(raw) == "FAQ: ответы\nВыпустят ли меня на границе?"


def test_removes_no_access_system_notice_only():
    assert clean_markdown_for_rag("Полезный текст\n\nNo access\n\nЕще текст") == "Полезный текст\n\nЕще текст"


def test_removes_sources_section_when_it_only_contains_file_and_telegram_noise():
    raw = """# Инструкция

Полезный текст.

### Источники и полезные ресурсы
- [Скачать PDF](https://example.org/doc.pdf) 211.6KB
- 802.5KB
- @pogran_unban_bot
- You are invited to the channel

### Следующий раздел
Содержимое раздела.
"""
    cleaned = clean_markdown_for_rag(raw)
    assert "### Источники" not in cleaned
    assert "doc.pdf" not in cleaned
    assert "pogran_unban_bot" not in cleaned
    assert "You are invited" not in cleaned
    assert "### Следующий раздел" in cleaned
    assert "Содержимое раздела." in cleaned


def test_keeps_sources_section_with_relevant_non_file_source():
    raw = "### Источники\n- Закон о воинской обязанности: https://example.org/law"
    assert "### Источники" in clean_markdown_for_rag(raw)
