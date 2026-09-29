"""Conservative Markdown cleanup for Notion exports used in RAG pipelines."""

from __future__ import annotations

import re


_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_BASE64_IMAGE = re.compile(r"!\[[^\]]*\]\(data:image/[a-zA-Z0-9.+-]+;base64,[^)]*\)", re.I)
_NOTION_EMOJI = re.compile(r"!\[[^\]]*\]\(https?://notion-emojis\.s3[-.]?[^)]*\)", re.I)
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_PVS = re.compile(r"\?pvs=\d+", re.I)
_NOTION_INTERNAL = re.compile(r"(?:https?://[^\s)]*)?/[0-9a-f]{20,}(?:\?[^\s)]*)?#[0-9a-f]{8,}[^\s)]*", re.I)
_NOTION_HASH = re.compile(r"#[0-9a-f]{8,}(?:-[0-9a-f]{4,})*", re.I)
_TOC = re.compile(r"^\s*(?:>\s*)?(?:#{1,6}\s*)?содержание\s*:?[ \t]*$", re.I)
_DONATION = re.compile(r"мы будем рады, если вы поддержите|криптовалюта\s*:", re.I)
_PDF_DOWNLOAD = re.compile(r"скачать.{0,100}\.pdf|\.pdf.{0,100}скачать", re.I)
_NOTION_ERROR_MARKERS = (
    re.compile(r"this page couldn['’]?t be found", re.I),
    re.compile(r"you may not have access", re.I),
    re.compile(r"skip to content", re.I),
    re.compile(r"notion uses cookies", re.I),
)
_NO_ACCESS = re.compile(r"^\s*(?:>\s*)?no access\s*[.!]?\s*$", re.I)
_ZERO_WIDTH = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060\ufeff]")
_BRAND_PREFIX = re.compile(r"Идите\s+лесом(?=\s*(?:FAQ\s*:|[А-ЯЁA-Z]))", re.I)
_SOURCE_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s*источники(?:\s+и\s+полезные\s+ресурсы)?\s*#*\s*$", re.I)
_FILE_SIZE = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:KB|MB|КБ|МБ)\b", re.I)
_TELEGRAM_TECH = re.compile(r"@\w*(?:bot|_bot)\b|you are invited to the channel|t\.me/(?:joinchat|\+)", re.I)
_DOWNLOAD_TEXT = re.compile(r"скачать|download|открыть файл|download file", re.I)


def _clean_links(text: str) -> str:
    """Remove image syntax and internal Notion links while retaining useful labels."""
    text = _BASE64_IMAGE.sub("", text)
    text = _NOTION_EMOJI.sub("", text)
    text = re.sub(r"\[\s*!\[[^\]]*\]\([^)]*\)\s*([^\]]*)\]\([^)]*\)", r"\1", text)
    text = _IMAGE.sub("", text)
    text = _BRAND_PREFIX.sub("", text)
    text = _ZERO_WIDTH.sub("", text)

    def replace_link(match: re.Match[str]) -> str:
        label, url = match.group(1), match.group(2)
        if _NOTION_INTERNAL.search(url) or _NOTION_HASH.search(url):
            return label
        return f"[{label}]({_PVS.sub('', url)})"

    return _LINK.sub(replace_link, text)


def _is_toc_entry(line: str) -> bool:
    stripped = line.strip()
    return (
        not stripped
        or stripped.startswith(">")
        or re.match(r"^(?:[-*+]\s+|\d+[.)]\s+)", stripped) is not None
        or re.match(r"^\[[^]]+\]\(", stripped) is not None
    )


def _remove_blocks(lines: list[str]) -> list[str]:
    result: list[str] = []
    i = 0
    while i < len(lines):
        source_match = _SOURCE_HEADING.match(lines[i])
        if source_match:
            level = len(source_match.group(1))
            end = i + 1
            while end < len(lines):
                next_heading = re.match(r"^\s{0,3}(#{1,6})\s+", lines[end])
                if next_heading and len(next_heading.group(1)) <= level:
                    break
                end += 1
            section_content = [line for line in lines[i + 1 : end] if line.strip()]
            if all(_is_source_noise(line) for line in section_content):
                i = end
                continue
        if _TOC.match(lines[i]):
            i += 1
            while i < len(lines) and _is_toc_entry(lines[i]):
                i += 1
            continue
        if _DONATION.search(lines[i]):
            break
        if _NO_ACCESS.match(lines[i]):
            i += 1
            continue
        if _PDF_DOWNLOAD.search(lines[i]):
            i += 1
            continue
        result.append(lines[i])
        i += 1
    return result


def _is_source_noise(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    return bool(
        re.search(r"\.pdf(?:[?#)\s]|$)", stripped, re.I)
        or _PDF_DOWNLOAD.search(stripped)
        or _DOWNLOAD_TEXT.search(stripped)
        or _FILE_SIZE.search(stripped)
        or _TELEGRAM_TECH.search(stripped)
    )


def clean_markdown_for_rag(raw_text: str) -> str:
    """Clean a Notion Markdown export, preserving headings, lists, and tables."""
    if not isinstance(raw_text, str):
        raise TypeError("raw_text must be a string")
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    error_hits = sum(bool(marker.search(text)) for marker in _NOTION_ERROR_MARKERS)
    if error_hits >= 2 or _NOTION_ERROR_MARKERS[0].search(text):
        return ""
    text = _clean_links(text)
    text = "\n".join(_remove_blocks(text.split("\n")))
    return re.sub(r"\n{3,}", "\n\n", text).strip()
