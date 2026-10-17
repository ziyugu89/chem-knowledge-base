from __future__ import annotations

import json

from kb.config import CHUNK_OVERLAP, CHUNK_SIZE, EXTRACT_DIR
from kb.normalize import clean_page_text


def load_pages() -> list[dict]:
    pages: list[dict] = []
    for book in ("上", "中", "下"):
        path = EXTRACT_DIR / f"{book}.jsonl"
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    pages.append(json.loads(line))
    from kb.ingest_extra import load_extra_pages

    pages.extend(load_extra_pages())
    return pages


def _window(text: str, size: int, overlap: int) -> list[str]:
    if len(text) <= size:
        return [text] if text.strip() else []
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            cut = max(
                text.rfind("。", start, end),
                text.rfind("；", start, end),
                text.rfind("\n", start, end),
            )
            if cut > start + size // 2:
                end = cut + 1
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def _section_key(page: dict) -> tuple:
    return (
        page.get("book") or "",
        page.get("chapter") or "",
        page.get("section") or "",
        page.get("extra_id") or "",
    )


def _group_pages(pages: list[dict]) -> list[list[dict]]:
    groups: list[list[dict]] = []
    current: list[dict] = []
    current_key = None
    for page in pages:
        text = clean_page_text(page.get("text") or "")
        if len(text) < 40:
            continue
        cleaned = dict(page)
        cleaned["text"] = text
        key = _section_key(cleaned)
        if current and (key != current_key or cleaned["pdf_page"] > current[-1]["pdf_page"] + 1):
            groups.append(current)
            current = []
        current.append(cleaned)
        current_key = key
    if current:
        groups.append(current)
    return groups


def build_chunks(pages: list[dict] | None = None) -> list[dict]:
    pages = pages if pages is not None else load_pages()
    chunks: list[dict] = []
    cid = 0
    for group in _group_pages(pages):
        parts = []
        spans = []
        cursor = 0
        for page in group:
            text = page["text"]
            parts.append(text)
            spans.append((cursor, cursor + len(text), page))
            cursor += len(text) + 1
        body = "\n".join(parts)
        meta = group[0]
        if meta.get("book") in ("上", "中", "下"):
            heading = " ".join(
                x for x in [meta.get("book_title"), meta.get("chapter"), meta.get("section")] if x
            )
        else:
            heading = meta.get("book_title") or meta.get("chapter") or "补充资料"
        search_from = 0
        for piece in _window(body, CHUNK_SIZE, CHUNK_OVERLAP):
            if len(piece) < 40:
                continue
            idx = body.find(piece[: min(40, len(piece))], search_from)
            if idx < 0:
                idx = body.find(piece[: min(40, len(piece))])
            start = idx if idx >= 0 else search_from
            end = start + len(piece)
            search_from = max(start, search_from)
            covered = [p["pdf_page"] for s, e, p in spans if e > start and s < end]
            cid += 1
            chunks.append(
                {
                    "id": cid,
                    "book": meta.get("book"),
                    "book_title": meta.get("book_title"),
                    "chapter": meta.get("chapter") or "",
                    "section": meta.get("section") or "",
                    "pdf_name": meta.get("pdf_name"),
                    "pdf_page": covered[0] if covered else group[0]["pdf_page"],
                    "pdf_page_end": covered[-1] if covered else group[-1]["pdf_page"],
                    "print_page": meta.get("print_page"),
                    "text": f"{heading}\n{piece}" if heading else piece,
                    "snippet": piece,
                }
            )
    return chunks
