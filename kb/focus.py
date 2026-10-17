from __future__ import annotations

import re

import jieba

from kb.synonyms import CUSTOM_WORDS, SYNONYMS

_STOP = {
    "什么", "哪些", "怎么", "如何", "主要", "相关", "介绍", "说明", "请问", "一下",
    "这个", "一种", "有哪些", "是什么", "为什么", "各自", "以及", "还有", "作为",
    "替代品", "常见", "注意点", "注意", "要求",
}

_ASPECT_ALIAS = {
    "成分": ["成分", "组成", "化学式", "主要成分为"],
    "用途": ["用途", "应用", "用于", "用作"],
    "性质": ["性质", "特性", "性能", "熔点", "硬度"],
    "特性": ["特性", "性质", "性能", "不黏", "不粘", "耐腐蚀", "耐热"],
    "生产": ["生产", "制取", "制备", "路线", "工艺"],
    "路线": ["路线", "方法", "萤石法", "工艺"],
    "设备": ["设备", "反应器", "回转炉", "吸收塔"],
    "安全": ["安全", "防护", "腐蚀", "中毒", "泄漏"],
    "区别": ["区别", "不同", "差异", "相比", "ODP", "GWP"],
}

_SKIP = (
    "矿床", "围岩", "脉状", "交代型", "浸染状", "编写委员会",
    "参考文献", "ISBN", "责任编辑", "高等教育",
    "本章主要讨论", "本章主要", "本章将", "本节介绍", "见图", "如图",
    "续表", "生产企业", "质量分数/%",
)

_OFFTOPIC = {
    "性质": ("涂料", "分散液", "微粉", "选矿", "跳汰", "手选"),
    "特性": ("涂料", "分散液", "微粉", "喷涂", "浓缩釜"),
    "用途": ("选矿", "跳汰", "手选", "矿床"),
    "成分": ("选矿", "跳汰", "手选", "矿床"),
    "区别": ("专利", "产能", "产量", "装置能力"),
    "路线": ("杂质", "专利"),
    "设备": ("产量变化",),
    "安全": ("产量", "专利"),
}

_SENT_SPLIT = re.compile(r"(?<=[。！？；])")


def parse_question(question: str) -> dict:
    q = question or ""
    for w in CUSTOM_WORDS:
        jieba.add_word(w)
    words = [t.strip() for t in jieba.lcut(q) if t.strip()]
    words += re.findall(r"[A-Za-z][A-Za-z0-9\-]{1,}", q)
    keys = [w for w in words if w not in _STOP and len(w) >= 2]
    seen: list[str] = []
    for w in keys:
        if w not in seen:
            seen.append(w)
    keys = seen
    topics: list[str] = []
    for w in keys:
        if w in _ASPECT_ALIAS:
            continue
        topics.append(w)
        for alias in SYNONYMS.get(w, [])[:3]:
            if alias not in topics:
                topics.append(alias)
    aspects: list[str] = []
    for name, aliases in _ASPECT_ALIAS.items():
        if name in q or any(a in q for a in aliases[:2]):
            for a in aliases:
                if a not in aspects:
                    aspects.append(a)
    if not topics:
        topics = keys[:6]
    return {"question": q, "topics": topics[:10], "aspects": aspects[:12], "keys": keys[:14]}


def _loc(chunk: dict) -> str:
    return "".join(
        str(chunk.get(k) or "")
        for k in ("book_title", "chapter", "section", "book")
    )


def chunk_focus_score(chunk: dict, focus: dict) -> float:
    text = chunk.get("text") or ""
    loc = _loc(chunk)
    blob = loc + "\n" + text[:900]
    topics = focus.get("topics") or []
    aspects = focus.get("aspects") or []
    topic_hits = sum(1 for t in topics if t and t in blob)
    if topics and topic_hits == 0:
        return -1.0
    score = 0.18 * min(topic_hits, 4)
    loc_topic = sum(1 for t in topics if t and t in loc)
    score += 0.16 * loc_topic
    aspect_hits = sum(1 for a in aspects if a and a in blob)
    score += 0.10 * min(aspect_hits, 4)
    loc_aspect = sum(1 for a in aspects if a and a in loc)
    score += 0.14 * loc_aspect
    q = focus.get("question") or ""
    for name, noises in _OFFTOPIC.items():
        if name in q or any(a in q for a in _ASPECT_ALIAS.get(name, [])[:2]):
            if any(n in blob[:400] for n in noises) and not any(n in q for n in noises):
                score -= 0.36
    if "矿床" in text[:160] and "矿床" not in q:
        score -= 0.28
    if "选矿" in loc and not any(x in q for x in ("选矿", "采选")):
        score -= 0.20
    if "萤石法" in loc and "萤石法" not in q and "氢氟酸" not in q:
        score -= 0.20
    if any(a in (focus.get("aspects") or []) for a in ("性质", "特性", "性能")):
        if "的性质" in text or "的特性" in text or "塑料王" in text:
            score += 0.28
    if any(a in (focus.get("aspects") or []) for a in ("用途", "应用")):
        if "的用途" in text or "主要用于" in text:
            score += 0.16
    if "路线" in q and "路线" in loc:
        score += 0.22
    if any(x in q for x in ("路线", "设备", "安全")) and "概述" in loc:
        score -= 0.16
    if "设备" in q and "设备" in loc:
        score += 0.30
    if "设备" in q and any(x in blob for x in ("回转炉", "回转窑", "吸收塔", "反应器")):
        score += 0.18
    if "安全" in q and ("安全" in loc or "劳动保护" in loc):
        score += 0.30
    if "安全" in q and any(x in blob for x in ("安全", "防护", "中毒", "泄漏")):
        score += 0.12
    if any(x in q for x in ("ODS", "HCFC", "HFC")):
        if "展望" in loc:
            score -= 0.22
        if "消耗臭氧" in text or "ODP" in text:
            score += 0.18
    if any(x in q for x in ("PTFE", "聚四氟乙烯")) and any(a in q for a in ("特性", "性质", "性能")):
        if "化学稳定性" in text or "塑料王" in text:
            score += 0.20
    return score


def split_sents(text: str) -> list[str]:
    raw = text or ""
    raw = re.sub(r"第[一二三四五六七八九十0-9]+[章节][^\n。；]{0,24}", "。", raw)
    raw = re.sub(r"([\u4e00-\u9fff])[.\．](?=[\u4e00-\u9fffA-Za-z])", r"\1。", raw)
    raw = raw.replace("\n", "。")
    out = []
    for sent in _SENT_SPLIT.split(raw):
        sent = re.sub(r"\s+", "", sent.strip("。； "))
        if sent:
            out.append(sent)
    return out


def is_noise(sent: str) -> bool:
    if any(s in sent for s in _SKIP):
        return True
    if re.search(r"本章.{0,8}讨论", sent):
        return True
    if re.match(r"^[一二三四五六七八九十]+、", sent) and ("矿床" in sent or "形成" in sent):
        return True
    if re.search(r"图\d+\.|表\d+\.", sent) and len(sent) < 40:
        return True
    if "大金工业" in sent or "Monteflon" in sent or "粗酸泵" in sent:
        return True
    if re.search(r"熔点为一?\s*-?14", sent):
        return True
    return False


def sent_score(sent: str, focus: dict, loc_has_topic: bool = False) -> float:
    if len(sent) < 16:
        return -99.0
    if is_noise(sent):
        return -99.0
    if re.match(r"^[一二三四五六七八九十]+、.{0,16}$", sent):
        return -99.0
    topics = focus.get("topics") or []
    aspects = focus.get("aspects") or []
    topic_hits = sum(1 for t in topics if t and t in sent)
    aspect_hits = sum(1 for a in aspects if a and a in sent)
    if topics and topic_hits == 0:
        if not (loc_has_topic and aspect_hits):
            return -99.0
    score = topic_hits * 3.0
    score += aspect_hits * 2.2
    if "主要成分" in sent or "化学式" in sent:
        score += 3.0
    if "用于" in sent or "用途" in sent or "应用" in sent:
        score += 2.0
    if "塑料王" in sent or "被称为" in sent:
        score += 1.5
    q = focus.get("question") or ""
    if ("PTFE" in q or "聚四氟乙烯" in q) and "四氟乙烯" in sent and "聚四氟乙烯" not in sent and "PTFE" not in sent:
        score -= 6.0
    if sent.count("%") >= 3 or sent.count("R1") >= 2:
        score -= 4.0
    if len(sent) > 220:
        score -= 1.8
    score += min(len(sent), 90) * 0.01
    return score


def pick_sentences(texts: list[str], focus: dict, limit: int = 6) -> list[str]:
    scored: list[tuple[float, str]] = []
    seen: set[str] = set()
    topics = focus.get("topics") or []
    for text in texts:
        loc_has_topic = any(t in (text or "")[:120] for t in topics if t)
        for sent in split_sents(text):
            key = sent[:26]
            if key in seen:
                continue
            s = sent_score(sent, focus, loc_has_topic=loc_has_topic)
            if s < 0 or is_noise(sent):
                continue
            seen.add(key)
            scored.append((s, sent))
    scored.sort(key=lambda x: x[0], reverse=True)
    aspects = [a for a in (focus.get("aspects") or []) if len(a) >= 2]
    picked: list[str] = []
    covered: set[str] = set()
    if aspects:
        for asp in aspects:
            for s, sent in scored:
                if asp in sent and sent not in picked:
                    picked.append(sent)
                    covered.add(asp)
                    break
            if len(picked) >= limit:
                return picked
    for _s, sent in scored:
        if sent not in picked:
            picked.append(sent)
        if len(picked) >= limit:
            break
    return picked
