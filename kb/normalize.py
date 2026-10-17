from __future__ import annotations

import re

_CHAPTER_LINE = re.compile(
    r"^第\s*([一二三四五六七八九十百零〇0-9]+)\s*章\s*(.*)$"
)
_SECTION_LINE = re.compile(
    r"^第\s*([一二三四五六七八九十百零〇0-9]+)\s*节\s*(.*)$"
)
_PRINT_PAGE = re.compile(
    r"[·•．.\s]{0,3}(\d{1,3})[·•．.\s]{0,3}$"
)
_LATIN_GAP = re.compile(r"\b([A-Z0-9])\s+(?=[A-Z0-9]\b)")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")
_JUNK_HEADER = re.compile(
    r"^(氟化工生产技术[（(][上中下][)）]|高等教育|应用化工类|·\s*$)"
)
_PAGE_MARK = re.compile(r"^[·•.\s]*\d{1,3}[·•.\s]*$")
_RUNNING_HEAD = re.compile(r"^氟化工生产技术[（(][上中下][)）]$")


def clean_page_text(text: str) -> str:
    text = merge_broken_lines(normalize_text(text or ""))
    kept: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        compact = s.replace(" ", "")
        if _PAGE_MARK.fullmatch(s) or _PAGE_MARK.fullmatch(compact):
            continue
        if _RUNNING_HEAD.fullmatch(compact) or _JUNK_HEADER.match(s):
            continue
        if len(s) <= 2 and s in "·•.-—":
            continue
        kept.append(s)
    return "\n".join(kept).strip()


def fullwidth_to_halfwidth(text: str) -> str:
    chars = []
    for ch in text:
        code = ord(ch)
        if code == 0x3000:
            chars.append(" ")
        elif 0xFF01 <= code <= 0xFF5E:
            chars.append(chr(code - 0xFEE0))
        else:
            chars.append(ch)
    return "".join(chars)


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\u3000", " ").replace("\xa0", " ")
    text = fullwidth_to_halfwidth(text)
    text = text.replace("畅", ".").replace("唱", "-").replace("枟", "《").replace("枠", "》")
    text = text.replace("倡", "").replace("枙", "").replace("枛", "")
    text = text.replace("～", "~").replace("—", "-").replace("–", "-")
    while True:
        nxt = _LATIN_GAP.sub(r"\1", text)
        if nxt == text:
            break
        text = nxt
    text = _MULTI_SPACE.sub(" ", text)
    return text.strip()


def merge_broken_lines(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines()]
    merged: list[str] = []
    for line in lines:
        if not line:
            if merged and merged[-1] != "":
                merged.append("")
            continue
        if _JUNK_HEADER.match(line):
            continue
        if merged and merged[-1] and _should_join(merged[-1], line):
            merged[-1] = merged[-1] + line
        else:
            merged.append(line)
    return "\n".join(merged).strip()


def _should_join(prev: str, cur: str) -> bool:
    if len(prev) <= 2:
        return False
    if _CHAPTER_LINE.match(prev) or _SECTION_LINE.match(prev):
        return False
    if _CHAPTER_LINE.match(cur) or _SECTION_LINE.match(cur):
        return False
    last = prev[-1]
    if last in "。！？；：…」』）)]、":
        return False
    if last in ".!?;:" and not last == ".":
        return False
    return True


def detect_heading(text: str) -> tuple[str | None, str | None]:
    chapter = None
    section = None
    for raw in text.splitlines()[:12]:
        line = raw.strip().replace(" ", "")
        m = _CHAPTER_LINE.match(line) or _CHAPTER_LINE.match(raw.strip())
        if m:
            title = (m.group(2) or "").strip()
            chapter = f"第{m.group(1)}章" + (f" {title}" if title else "")
            continue
        m = _SECTION_LINE.match(line) or _SECTION_LINE.match(raw.strip())
        if m:
            title = (m.group(2) or "").strip()
            section = f"第{m.group(1)}节" + (f" {title}" if title else "")
    return chapter, section


def detect_print_page(text: str) -> int | None:
    for raw in text.splitlines()[-8:] + text.splitlines()[:6]:
        compact = raw.strip().replace(" ", "")
        m = re.fullmatch(r"[·•.]*(\d{1,3})[·•.]*", compact)
        if m:
            n = int(m.group(1))
            if 1 <= n <= 800:
                return n
    return None


def cn_num_to_int(s: str) -> int | None:
    s = s.strip()
    if s.isdigit():
        return int(s)
    table = {"零": 0, "〇": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    if s in table:
        return table[s]
    if s.startswith("十"):
        return 10 + table.get(s[1:], 0)
    if "十" in s:
        a, b = s.split("十", 1)
        return table.get(a, 0) * 10 + table.get(b, 0)
    return None
