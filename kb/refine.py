from __future__ import annotations

import re

from kb.chunk import load_pages
from kb.focus import parse_question, pick_sentences
from kb.normalize import clean_page_text
from kb.retrieve import Hit, clip_sentences

_PAGE_CACHE: dict[tuple, dict] | None = None


def _page_cache() -> dict[tuple, dict]:
    global _PAGE_CACHE
    if _PAGE_CACHE is None:
        _PAGE_CACHE = {}
        for page in load_pages():
            text = clean_page_text(page.get("text") or "")
            if text:
                _PAGE_CACHE[(page.get("book"), int(page.get("pdf_page") or 0))] = {**page, "text": text}
    return _PAGE_CACHE


def reset_page_cache() -> None:
    global _PAGE_CACHE
    _PAGE_CACHE = None


def _relevant_hits(question: str, hits: list[Hit]) -> list[Hit]:
    focus = parse_question(question)
    kept: list[Hit] = []
    for hit in hits:
        if pick_sentences([hit.snippet or hit.text or ""], focus, limit=1):
            kept.append(hit)
    return kept or list(hits[:2])


def sources_from_hits(hits: list[Hit], question: str = "") -> list[dict]:
    focus = parse_question(question)
    items = []
    for hit in hits[:4]:
        picked = pick_sentences([hit.snippet or hit.text or ""], focus, limit=3)
        snippet = "".join(picked) if picked else clip_sentences(hit.snippet, 280)
        items.append(
            {
                "cite": hit.cite(),
                "snippet": clip_sentences(snippet, 320),
                "score": round(float(hit.score), 4),
            }
        )
    return items


def _group_body(question: str, sents: list[str]) -> str:
    focus = parse_question(question)
    labels = []
    if any(a in (focus.get("aspects") or []) for a in ("成分", "化学式", "组成")):
        labels.append(("成分", ("成分", "组成", "化学式", "主要成分为", "CaF2", "氟化钙")))
    if any(a in (focus.get("aspects") or []) for a in ("性质", "特性", "性能")):
        labels.append(("性质", ("性质", "特性", "性能", "熔点", "硬度", "不黏", "不粘", "耐")))
    if any(a in (focus.get("aspects") or []) for a in ("用途", "应用", "用于")):
        labels.append(("用途", ("用途", "应用", "用于", "用作")))
    if any(a in (focus.get("aspects") or []) for a in ("路线", "生产", "制取", "萤石法")):
        labels.append(("生产路线", ("路线", "萤石法", "反应", "工艺", "制取")))
    if any(a in (focus.get("aspects") or []) for a in ("设备", "反应器")):
        labels.append(("设备", ("设备", "反应器", "回转炉", "吸收塔")))
    if any(a in (focus.get("aspects") or []) for a in ("安全", "防护")):
        labels.append(("安全", ("安全", "防护", "腐蚀", "中毒", "泄漏")))
    if any(a in (focus.get("aspects") or []) for a in ("区别", "ODP", "GWP")):
        labels.append(("区别", ("区别", "不同", "ODP", "GWP", "相比")))
    if not labels or len(sents) == 1:
        return "\n\n".join(sents)
    used: set[int] = set()
    parts: list[str] = []
    for title, keys in labels:
        chosen = []
        for i, sent in enumerate(sents):
            if i in used:
                continue
            if any(k in sent for k in keys):
                chosen.append(sent)
                used.add(i)
        if chosen:
            parts.append(f"【{title}】" + "".join(chosen))
    leftover = [s for i, s in enumerate(sents) if i not in used]
    if leftover and not parts:
        return "\n\n".join(leftover)
    if leftover:
        parts.append("".join(leftover))
    return "\n\n".join(parts) if parts else "\n\n".join(sents)


def synthesize_answer(question: str, hits: list[Hit]) -> str:
    if not hits:
        return "向量库中没有检索到足够相关的知识片段。请换个更具体的物质、工艺或设备名称。"
    focus = parse_question(question)
    texts = []
    for h in hits:
        head = " ".join(x for x in [h.chapter, h.section] if x)
        body = h.snippet or h.text or ""
        texts.append(f"{head}\n{body}")
    picked = pick_sentences(texts, focus, limit=6)
    if not picked:
        loose = parse_question(question)
        loose["aspects"] = []
        picked = pick_sentences(texts, loose, limit=3)
    if not picked:
        picked = [clip_sentences(re.sub(r"第[一二三四五六七八九十0-9]+[章节][^\n]{0,20}", "", hits[0].snippet), 180)]
    body = _group_body(question, picked)
    cites = "；".join(dict.fromkeys(h.cite() for h in hits[:3]))
    return f"{body}\n\n出处：{cites}"


def refine_passage(question: str, hits: list[Hit], limit: int = 820) -> dict:
    hits = _relevant_hits(question, hits)
    answer = synthesize_answer(question, hits)
    src = sources_from_hits(hits, question)
    return {
        "answer": answer,
        "source": src[0]["snippet"] if src else "",
        "cite": src[0]["cite"] if src else "",
        "hits": src,
    }
