"""Асинхронный обход сайта и сохранение страниц базы знаний в PostgreSQL."""

import asyncio
import hashlib
from collections import deque
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup
from markdownify import markdownify
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright
from sqlalchemy import func, select

from src.config import settings
from src.db.models import RawDocument
from src.db.session import AsyncSessionLocal


_CONTENT_SELECTORS = (
    "main",
    "article",
    "[role='main']",
    ".notion-page-content",
    ".notion-page",
)
_NON_CONTENT_TAGS = ("nav", "footer", "aside", "script", "style", "noscript", "iframe", "button")
_IGNORED_EXTENSIONS = (
    ".7z", ".css", ".doc", ".docx", ".gif", ".ico", ".jpeg", ".jpg", ".js",
    ".json", ".pdf", ".png", ".ppt", ".pptx", ".rar", ".svg", ".zip",
)


def _normalize_url(url: str) -> str:
    """Убирает fragment и завершающие дублирующие слеши из URL."""
    url, _fragment = urldefrag(url)
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", parsed.query, ""))


def _is_crawlable(url: str, start_url: str) -> bool:
    """Ограничивает обход исходным сайтом и исключает ссылки на файлы."""
    parsed = urlparse(url)
    start = urlparse(start_url)
    if parsed.scheme not in ("http", "https") or parsed.netloc.lower() != start.netloc.lower():
        return False
    return not parsed.path.lower().endswith(_IGNORED_EXTENSIONS)


def _extract_page(html: str) -> tuple[str, str, list[str]]:
    """Возвращает заголовок, очищенный HTML содержимого и ссылки страницы."""
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("h1") or soup.find("title")
    title = title_tag.get_text(" ", strip=True) if title_tag else "Без названия"
    # Собираем ссылки до очистки: ссылки навигации тоже могут вести на статьи.
    links: list[str] = [
        str(href)
        for link in soup.select("a[href]")
        if (href := link.get("href")) is not None
    ]

    content = None
    for selector in _CONTENT_SELECTORS:
        content = soup.select_one(selector)
        if content:
            break
    content = content or soup.body or soup

    # Удаляем глобальные элементы и управляющие элементы, не относящиеся к статье.
    for tag in content.find_all(_NON_CONTENT_TAGS):
        tag.decompose()
    for node in content.select("[aria-hidden='true'], [role='navigation'], .sidebar, .navigation"):
        node.decompose()

    clean_html = "".join(str(child) for child in content.contents).strip()
    return title, clean_html, links


async def _save_document(url: str, title: str, html_content: str, markdown_content: str) -> None:
    """Сохраняет страницу, создавая новую версию при изменении содержимого."""
    new_hash = hashlib.md5(markdown_content.encode("utf-8")).hexdigest()

    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(RawDocument).where(
                    RawDocument.url == url,
                    RawDocument.is_active == True,  # noqa: E712
                )
            )
            existing_doc = result.scalar_one_or_none()

            if existing_doc is None:
                session.add(
                    RawDocument(
                        url=url,
                        title=title,
                        html_content=html_content,
                        markdown_content=markdown_content,
                        content_hash=new_hash,
                        is_active=True,
                        version=1,
                        last_parsed_at=func.now(),
                    )
                )
                message = f"[СОЗДАНО v1] {title}"
            elif existing_doc.content_hash == new_hash:
                existing_doc.last_parsed_at = func.now()
                message = f"[БЕЗ ИЗМЕНЕНИЙ (last_parsed_at обновлен)] {title}"
            else:
                existing_doc.is_active = False
                version = existing_doc.version + 1
                session.add(
                    RawDocument(
                        url=url,
                        title=title,
                        html_content=html_content,
                        markdown_content=markdown_content,
                        content_hash=new_hash,
                        is_active=True,
                        version=version,
                        last_parsed_at=func.now(),
                    )
                )
                message = f"[НОВАЯ ВЕРСИЯ v{version}] {title}"

            await session.commit()
            print(message)
        except Exception:
            await session.rollback()
            raise


async def run_scraper(start_url: str | None = None) -> None:
    """Обходит ссылки одного сайта и сохраняет найденные страницы.

    Если URL не передан, используется ``settings.START_URL``.
    """
    start_url = _normalize_url(start_url or settings.START_URL)
    if not urlparse(start_url).netloc:
        raise ValueError(f"Некорректный START_URL: {start_url!r}")

    pending = deque([start_url])
    visited: set[str] = set()

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            while pending:
                url = pending.popleft()
                if url in visited or not _is_crawlable(url, start_url):
                    continue
                visited.add(url)

                try:
                    response = await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
                    # networkidle подходит для большинства страниц, но некоторые SPA
                    # держат соединения постоянно; тогда используем уже загруженный DOM.
                    try:
                        await page.wait_for_load_state("networkidle", timeout=10_000)
                    except PlaywrightTimeoutError:
                        await page.wait_for_timeout(1_000)

                    if response is not None and response.status >= 400:
                        print(f"Пропуск HTTP {response.status}: {url}")
                        continue

                    title, html_content, hrefs = _extract_page(await page.content())
                    markdown_content = markdownify(html_content, heading_style="ATX").strip()

                    for href in hrefs:
                        next_url = _normalize_url(urljoin(url, href))
                        if next_url not in visited and _is_crawlable(next_url, start_url):
                            pending.append(next_url)

                    if markdown_content:
                        await _save_document(url, title, html_content, markdown_content)
                        print(f"Обработано: {len(visited)}, в очереди: {len(pending)}")
                except Exception as error:
                    print(f"Ошибка при обработке {url}: {error}")
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(run_scraper(settings.START_URL))
