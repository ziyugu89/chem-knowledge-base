from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path

from kb.config import EXTRA_DIR
from kb.normalize import clean_page_text, normalize_text

MAX_UPLOAD_BYTES = 12 * 1024 * 1024
MAX_CHARS = 200_000
MIN_CHARS = 40
_TEXT_EXT = {".txt", ".md", ".text", ".csv"}
_PDF_EXT = {".pdf"}


def _now_id() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:6]


def _doc_path(doc_id: str) -> Path:
    safe = re.sub(r"[^0-9A-Za-z_-]", "", doc_id)
    if not safe or safe != doc_id:
        raise ValueError("无效的资料编号")
    return EXTRA_DIR / f"{safe}.json"


def _split_pages(text: str, size: int = 1800, overlap: int = 80) -> list[str]:
    text = clean_page_text(text)
    if len(text) <= size:
        return [text] if text.strip() else []
    pages: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            cut = max(text.rfind("。", start, end), text.rfind("\n", start, end), text.rfind("；", start, end))
            if cut > start + size // 2:
                end = cut + 1
        piece = text[start:end].strip()
        if piece:
            pages.append(piece)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return pages


def _pages_payload(title: str, doc_id: str, source: str, pieces: list[str]) -> list[dict]:
    pages = []
    for i, piece in enumerate(pieces, 1):
        pages.append(
            {
                "book": "补充",
                "book_title": title,
                "pdf_name": source or f"{title}.txt",
                "pdf_page": i,
                "print_page": None,
                "chapter": title,
                "section": doc_id,
                "method": "extra",
                "text": piece,
                "chars": len(piece),
                "extra_id": doc_id,
            }
        )
    return pages


def _write_doc(doc: dict) -> None:
    EXTRA_DIR.mkdir(parents=True, exist_ok=True)
    path = _doc_path(doc["id"])
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def _public(doc: dict) -> dict:
    return {
        "id": doc.get("id"),
        "title": doc.get("title") or "",
        "source": doc.get("source") or "",
        "created": doc.get("created") or "",
        "pages": len(doc.get("pages") or []),
        "chars": int(doc.get("chars") or 0),
    }


def list_extra() -> list[dict]:
    items = []
    if not EXTRA_DIR.exists():
        return items
    for path in EXTRA_DIR.glob("*.json"):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(doc, dict) and doc.get("id"):
                items.append(_public(doc))
        except Exception:
            continue
    items.sort(key=lambda x: x.get("created") or "", reverse=True)
    return items


def extra_status() -> dict:
    items = list_extra()
    return {
        "docs": len(items),
        "chars": sum(int(x.get("chars") or 0) for x in items),
        "pages": sum(int(x.get("pages") or 0) for x in items),
        "items": items,
    }


def load_extra_pages() -> list[dict]:
    pages: list[dict] = []
    if not EXTRA_DIR.exists():
        return pages
    for path in sorted(EXTRA_DIR.glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for page in doc.get("pages") or []:
            if page.get("text"):
                pages.append(page)
    return pages


def save_text(title: str, text: str, source: str = "粘贴文本") -> dict:
    title = (title or "").strip() or "未命名资料"
    title = title[:80]
    raw = normalize_text(text or "")
    cleaned = clean_page_text(raw)
    if len(cleaned) < MIN_CHARS:
        raise ValueError(f"文本太短（至少 {MIN_CHARS} 字），无法入库")
    if len(cleaned) > MAX_CHARS:
        raise ValueError(f"单篇不超过 {MAX_CHARS} 字，请拆成多篇添加")
    pieces = _split_pages(cleaned)
    if not pieces:
        raise ValueError("没有可入库的正文")
    doc_id = _now_id()
    pages = _pages_payload(title, doc_id, source, pieces)
    doc = {
        "id": doc_id,
        "title": title,
        "source": source,
        "created": datetime.now().isoformat(timespec="seconds"),
        "chars": sum(p["chars"] for p in pages),
        "pages": pages,
    }
    _write_doc(doc)
    return _public(doc)


def _decode_bytes(data: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def _pdf_text(data: bytes) -> str:
    import pymupdf

    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
        try:
            parts = []
            for page in doc:
                parts.append(page.get_text("text") or "")
            return "\n".join(parts)
        finally:
            doc.close()
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"无法读取 PDF：{exc}") from exc


def save_upload(filename: str, data: bytes, title: str = "") -> dict:
    if not data:
        raise ValueError("文件是空的")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("文件太大，请小于 12 MB")
    name = Path(filename or "upload.txt").name
    ext = Path(name).suffix.lower()
    stem = Path(name).stem[:80]
    heading = (title or "").strip() or stem or "上传资料"
    if ext in _PDF_EXT:
        text = _pdf_text(data)
        source = name
        if len(clean_page_text(normalize_text(text))) < MIN_CHARS:
            raise ValueError("这个 PDF 几乎抽不出文字（多半是扫描件）。请先转成文本，或直接把内容粘贴进来。")
    elif ext in _TEXT_EXT or ext == "":
        text = _decode_bytes(data)
        source = name
    else:
        raise ValueError("目前支持 txt、md、pdf，或直接粘贴文本")
    return save_text(heading, text, source=source)


def delete_extra(doc_id: str) -> bool:
    path = _doc_path(doc_id)
    if not path.exists():
        return False
    path.unlink()
    return True
