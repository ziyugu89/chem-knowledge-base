from __future__ import annotations

import json
import pickle
import re
from dataclasses import asdict, dataclass

import jieba
import numpy as np
from rank_bm25 import BM25Okapi

from kb.chunk import build_chunks, load_pages
from kb.config import CANDIDATES, INDEX_FILE, INDEX_VERSION, TOP_K
from kb.focus import chunk_focus_score, parse_question
from kb.synonyms import CUSTOM_WORDS, expand_query
from kb.vectorstore import build_tfidf_matrix, cosine_scores, encode, load_vectors, save_vectors

_STOP = {
    "的", "了", "是", "在", "和", "与", "及", "或", "等", "为", "对", "中", "上", "下",
    "也", "就", "都", "而", "并", "被", "把", "由", "其", "这", "那", "一个", "可以",
    "以及", "如果", "因为", "所以", "通过", "进行", "使用", "具有", "主要", "一般",
}


def _ensure_jieba() -> None:
    jieba.initialize()
    for w in CUSTOM_WORDS:
        jieba.add_word(w)


def tokenize(text: str) -> list[str]:
    _ensure_jieba()
    return [t.strip() for t in jieba.lcut(text) if t.strip() and t not in _STOP and t != "\n"]


def stitch_texts(texts: list[str]) -> str:
    out = ""
    for raw in texts:
        text = re.sub(r"\n+", "\n", (raw or "").strip())
        if not text:
            continue
        if not out:
            out = text
            continue
        max_ol = min(len(out), len(text), 160)
        overlap = 0
        for n in range(max_ol, 24, -1):
            if out.endswith(text[:n]):
                overlap = n
                break
        piece = text[overlap:] if overlap else text
        if not piece:
            continue
        if out[-1] in "。！？；\n" or piece[0] in "。！？；\n一二三四五六七八九十（(":
            out = out.rstrip() + "\n" + piece.lstrip()
        else:
            out += piece
    return out.strip()


def clip_sentences(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = max(text.rfind("。", 0, limit), text.rfind("；", 0, limit))
    if cut < limit // 3:
        return text[:limit].rstrip("，、； ") + "。"
    return text[: cut + 1]


@dataclass
class Hit:
    id: int
    score: float
    book: str
    book_title: str
    chapter: str
    section: str
    pdf_name: str
    pdf_page: int
    pdf_page_end: int
    print_page: int | None
    text: str
    snippet: str

    def cite(self) -> str:
        end = self.pdf_page_end or self.pdf_page
        if self.book in ("上", "中", "下"):
            book = f"{self.book}册"
            loc = " · ".join(x for x in [book, self.chapter, self.section] if x)
            page = f"PDF第{self.pdf_page}页" if end <= self.pdf_page else f"PDF第{self.pdf_page}-{end}页"
            return f"{loc} {page}".strip()
        title = self.book_title or self.chapter or "补充资料"
        page = f"第{self.pdf_page}页" if end <= self.pdf_page else f"第{self.pdf_page}-{end}页"
        return f"补充资料 · {title} {page}".strip()

    def as_dict(self) -> dict:
        d = asdict(self)
        d["cite"] = self.cite()
        preview = d["snippet"]
        if len(preview) > 220:
            d["snippet"] = clip_sentences(preview, 220)
        return d


def collapse_hits(hits: list[Hit], keep: int = TOP_K) -> list[Hit]:
    if not hits:
        return []
    ranked = sorted(hits, key=lambda h: h.score, reverse=True)
    chosen: list[Hit] = []
    seen_pages: set[tuple] = set()
    for hit in ranked:
        page_key = (hit.book, hit.pdf_page)
        if page_key in seen_pages:
            continue
        too_close = False
        for kept in chosen:
            if hit.book == kept.book and abs(hit.pdf_page - kept.pdf_page) <= 1:
                if _similar(hit.snippet, kept.snippet):
                    too_close = True
                    break
        if too_close:
            continue
        seen_pages.add(page_key)
        chosen.append(hit)
        if len(chosen) >= keep:
            break
    chosen.sort(key=lambda h: h.score, reverse=True)
    return chosen[:keep]


def _similar(a: str, b: str) -> bool:
    sa, sb = set(a[:180]), set(b[:180])
    if not sa or not sb:
        return False
    return len(sa & sb) / len(sa | sb) > 0.72


def _merge_block(block: list[Hit]) -> Hit:
    first = block[0]
    snippet = stitch_texts([h.snippet for h in block])
    return Hit(
        id=first.id,
        score=max(h.score for h in block),
        book=first.book,
        book_title=first.book_title,
        chapter=first.chapter,
        section=first.section,
        pdf_name=first.pdf_name,
        pdf_page=min(h.pdf_page for h in block),
        pdf_page_end=max(h.pdf_page_end or h.pdf_page for h in block),
        print_page=first.print_page,
        text=snippet,
        snippet=snippet,
    )


class KnowledgeIndex:
    def __init__(self, chunks: list[dict], vocab=None, idf=None, matrix=None, tokenized=None):
        self.chunks = chunks
        self.tokenized = tokenized if tokenized is not None else [tokenize(c["text"]) for c in chunks]
        self.bm25 = BM25Okapi(self.tokenized) if chunks else None
        if vocab is None or idf is None or matrix is None:
            vocab, idf, matrix = build_tfidf_matrix(self.tokenized)
        self.vocab = vocab
        self.idf = idf
        self.matrix = matrix

    @property
    def vector_dim(self) -> int:
        return int(self.matrix.shape[1]) if self.matrix is not None and self.matrix.size else 0

    def _hit_from_chunk(self, c: dict, score: float) -> Hit:
        return Hit(
            id=c["id"],
            score=float(score),
            book=c.get("book") or "",
            book_title=c.get("book_title") or "",
            chapter=c.get("chapter") or "",
            section=c.get("section") or "",
            pdf_name=c.get("pdf_name") or "",
            pdf_page=int(c.get("pdf_page") or 0),
            pdf_page_end=int(c.get("pdf_page_end") or c.get("pdf_page") or 0),
            print_page=c.get("print_page"),
            text=c["text"],
            snippet=c.get("snippet") or c["text"],
        )

    def search(self, query: str, top_k: int = TOP_K) -> list[Hit]:
        if not self.chunks or self.bm25 is None:
            return []
        expanded = expand_query(query)
        tokens = tokenize(expanded) or tokenize(query)
        bm25 = np.asarray(self.bm25.get_scores(tokens), dtype=np.float32)
        qvec = encode(tokens, self.vocab, self.idf)
        dense = cosine_scores(self.matrix, qvec)
        bm25_max = float(bm25.max()) if len(bm25) else 1.0
        bm25_n = bm25 / bm25_max if bm25_max > 0 else bm25
        hybrid = 0.50 * dense + 0.30 * bm25_n
        focus = parse_question(query)
        pool = max(CANDIDATES, 40)
        ranked = np.argsort(-hybrid)[:pool]
        scored: list[tuple[float, int]] = []
        for i in ranked:
            i = int(i)
            if hybrid[i] <= 0:
                continue
            bonus = chunk_focus_score(self.chunks[i], focus)
            if bonus < 0:
                continue
            scored.append((float(0.62 * hybrid[i] + bonus), i))
        if not scored:
            for i in ranked[: top_k * 3]:
                i = int(i)
                if hybrid[i] > 0:
                    scored.append((float(hybrid[i]), i))
        scored.sort(reverse=True)
        raw = [self._hit_from_chunk(self.chunks[i], s) for s, i in scored]
        hits = collapse_hits(raw, keep=top_k)
        return hits or raw[:top_k]


def build_and_save() -> KnowledgeIndex:
    pages = load_pages()
    if not pages:
        raise FileNotFoundError("尚未抽取教材文本，请先运行 python -m kb.extract")
    chunks = build_chunks(pages)
    tokenized = [tokenize(c["text"]) for c in chunks]
    vocab, idf, matrix = build_tfidf_matrix(tokenized)
    save_vectors(vocab, idf, matrix)
    index = KnowledgeIndex(chunks, vocab=vocab, idf=idf, matrix=matrix, tokenized=tokenized)
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    with INDEX_FILE.open("wb") as f:
        pickle.dump({"version": INDEX_VERSION, "chunks": chunks}, f)
    return index


def load_or_build(force: bool = False) -> KnowledgeIndex:
    packed = None if force else load_vectors()
    if not force and INDEX_FILE.exists() and packed is not None:
        try:
            with INDEX_FILE.open("rb") as f:
                payload = pickle.load(f)
            chunks = payload.get("chunks") if isinstance(payload, dict) else None
            if payload.get("version") == INDEX_VERSION and chunks:
                vocab, idf, matrix = packed
                if matrix.shape[0] == len(chunks):
                    return KnowledgeIndex(chunks, vocab=vocab, idf=idf, matrix=matrix)
        except Exception:
            pass
    return build_and_save()


def extract_ready() -> dict:
    from kb.config import BOOK_META, EXTRACT_DIR
    from kb.ingest_extra import extra_status

    info = {}
    for book in BOOK_META:
        path = EXTRACT_DIR / f"{book}.jsonl"
        if not path.exists():
            info[book] = {"pages": 0, "chars": 0, "ready": False}
            continue
        pages = 0
        chars = 0
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    pages += 1
                    try:
                        chars += int(json.loads(line).get("chars") or 0)
                    except Exception:
                        pass
        info[book] = {"pages": pages, "chars": chars, "ready": pages > 0}
    extra = extra_status()
    info["extra"] = {
        "pages": extra["pages"],
        "chars": extra["chars"],
        "ready": extra["docs"] > 0,
        "docs": extra["docs"],
        "items": extra["items"],
    }
    return info


if __name__ == "__main__":
    idx = build_and_save()
    print(f"索引完成：{len(idx.chunks)} 个片段")
