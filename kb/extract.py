from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pymupdf

from kb.config import BOOK_META, EXTRACT_DIR, ROOT
from kb.normalize import detect_heading, detect_print_page, merge_broken_lines, normalize_text


def find_pdfs() -> dict[str, Path]:
    found: dict[str, Path] = {}
    candidates = list(ROOT.glob("*.pdf")) + list((ROOT / "docs").glob("*.pdf"))
    for path in candidates:
        name = path.name
        for key in ("上", "中", "下"):
            if key in name and key not in found:
                found[key] = path
    return found


def _page_text_pymupdf(page) -> str:
    return (page.get_text("text") or "").strip()


def _pixmap_to_bgr(pix):
    import cv2
    import numpy as np

    h, w, n = pix.height, pix.width, pix.n
    buf = np.frombuffer(pix.samples, dtype=np.uint8).copy()
    if n <= 1 or pix.colorspace is None:
        gray = buf.reshape(h, w)
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    img = buf.reshape(h, w, n)
    if n == 4:
        return cv2.cvtColor(img[:, :, :3], cv2.COLOR_RGB2BGR)
    return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)


def _page_image(page):
    try:
        images = page.get_images()
        if images:
            xref = images[0][0]
            pix = pymupdf.Pixmap(page.parent, xref)
            if pix.width >= 600:
                return _pixmap_to_bgr(pix)
    except Exception:
        pass
    pix = page.get_pixmap(matrix=pymupdf.Matrix(2.0, 2.0), colorspace=pymupdf.csGRAY)
    return _pixmap_to_bgr(pix)


def _ocr_engine():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def ocr_page(ocr, page) -> str:
    import cv2

    img = _page_image(page)
    h, w = img.shape[:2]
    scale = 1680.0 / max(h, w)
    if scale < 1:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    result, _elapse = ocr(img, use_cls=False)
    if not result:
        return ""
    lines = []
    for item in result:
        text = ""
        score = 1.0
        if isinstance(item, dict):
            text = str(item.get("text") or item.get("txt") or "")
            score = item.get("score", 1.0)
        elif isinstance(item, (list, tuple)):
            if len(item) >= 2 and isinstance(item[1], str):
                text = item[1]
                score = item[2] if len(item) > 2 else 1.0
            elif len(item) >= 1 and isinstance(item[0], str):
                text = item[0]
                score = item[1] if len(item) > 1 else 1.0
        try:
            score_f = float(score)
        except (TypeError, ValueError):
            score_f = 1.0
        if text and score_f >= 0.35:
            lines.append(text)
    return "\n".join(lines)


def _load_done(path: Path) -> dict[int, dict]:
    done = {}
    if not path.exists():
        return done
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            done[int(row["pdf_page"])] = row
    return done


def _write_all(path: Path, rows: dict[int, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for page in sorted(rows):
            f.write(json.dumps(rows[page], ensure_ascii=False) + "\n")
    tmp.replace(path)


def extract_book(book_key: str, pdf_path: Path, force: bool = False) -> Path:
    out_path = EXTRACT_DIR / f"{book_key}.jsonl"
    doc = pymupdf.open(pdf_path)
    rows = {} if force else _load_done(out_path)
    need_ocr = False
    sample_pages = list(range(min(8, doc.page_count)))
    text_hits = 0
    for i in sample_pages:
        if len(_page_text_pymupdf(doc[i])) > 80:
            text_hits += 1
    if text_hits < max(1, len(sample_pages) // 3):
        need_ocr = True

    ocr = None
    if need_ocr:
        pending = [i for i in range(doc.page_count) if (i + 1) not in rows]
        if pending:
            print(f"[{book_key}] 扫描版 PDF，使用 OCR，共 {doc.page_count} 页，待处理 {len(pending)} 页", flush=True)
            ocr = _ocr_engine()
        else:
            print(f"[{book_key}] OCR 已完成，跳过", flush=True)
    else:
        print(f"[{book_key}] 可提取文本，共 {doc.page_count} 页", flush=True)

    chapter = BOOK_META[book_key]["label"]
    section = ""
    started = time.time()
    for i in range(doc.page_count):
        pdf_page = i + 1
        if pdf_page in rows and not force:
            ch = rows[pdf_page].get("chapter")
            se = rows[pdf_page].get("section")
            if ch:
                chapter = ch
            if se:
                section = se
            continue

        page = doc[i]
        try:
            if need_ocr:
                raw = ocr_page(ocr, page)
                method = "ocr"
            else:
                raw = _page_text_pymupdf(page)
                method = "text"
        except Exception as exc:
            print(f"[{book_key}] 第 {pdf_page} 页失败：{exc}，改用渲染重试", flush=True)
            try:
                pix = page.get_pixmap(matrix=pymupdf.Matrix(2.0, 2.0), colorspace=pymupdf.csGRAY)
                img = _pixmap_to_bgr(pix)
                result, _ = ocr(img, use_cls=False) if ocr else (None, None)
                raw = "\n".join(str(x[1]) for x in (result or []) if isinstance(x, (list, tuple)) and len(x) > 1)
                method = "ocr"
            except Exception as exc2:
                print(f"[{book_key}] 第 {pdf_page} 页仍失败：{exc2}", flush=True)
                raw = ""
                method = "failed"

        text = normalize_text(raw)
        if method == "text":
            text = merge_broken_lines(text)
        ch, se = detect_heading(text)
        if ch:
            chapter = ch
        if se:
            section = se
        print_page = detect_print_page(raw) or detect_print_page(text)
        rows[pdf_page] = {
            "book": book_key,
            "book_title": BOOK_META[book_key]["title"],
            "pdf_name": pdf_path.name,
            "pdf_page": pdf_page,
            "print_page": print_page,
            "chapter": chapter,
            "section": section,
            "method": method,
            "text": text,
            "chars": len(text),
        }
        if pdf_page % 5 == 0 or pdf_page == doc.page_count:
            _write_all(out_path, rows)
            elapsed = time.time() - started
            done_n = sum(1 for k in rows if k <= pdf_page)
            speed = done_n / max(elapsed, 0.1)
            remain = (doc.page_count - done_n) / max(speed, 0.01)
            print(
                f"[{book_key}] {pdf_page}/{doc.page_count} 页  {len(text)}字  "
                f"{speed:.2f}页/秒  预计剩余 {remain/60:.1f} 分钟",
                flush=True,
            )

    _write_all(out_path, rows)
    doc.close()
    print(f"[{book_key}] 完成 -> {out_path}", flush=True)
    return out_path


def extract_all(books: list[str] | None = None, force: bool = False) -> list[Path]:
    pdfs = find_pdfs()
    if not pdfs:
        raise FileNotFoundError("未找到《氟化工生产技术》PDF，请放在项目根目录或 docs/ 下")
    targets = books or list(pdfs)
    paths = []
    for key in targets:
        if key not in pdfs:
            print(f"跳过 {key}：未找到对应 PDF", flush=True)
            continue
        paths.append(extract_book(key, pdfs[key], force=force))
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="抽取 / OCR 三册教材")
    parser.add_argument("--book", choices=["上", "中", "下"], action="append")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    extract_all(args.book, force=args.force)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
