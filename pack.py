from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "氟化工生产技术知识库.zip"
SKIP_DIR = {".venv", "__pycache__", ".git", ".ocr_cache"}
# 对方自己有教材 PDF，不打进压缩包，减小体积也避免整书外传。
SKIP_SUFFIX = {".pdf", ".pyc", ".tmp", ".zip"}
SKIP_NAMES = {OUT.name, ".env"}
SKIP_PREFIX = ("_ocr", "_pdf", "_shang", "_zhong", "_xia", "_search", "_rag", "_check", "_extra_qc")
KEEP_ROOT = {
    "app.py",
    "pack.py",
    "README.md",
    "requirements.txt",
    "requirements-ingest.txt",
    ".env.example",
    ".gitignore",
    "启动知识库.bat",
    "打包发送.bat",
    "start.sh",
    "给同事.txt",
}


def keep(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in SKIP_DIR for part in rel.parts):
        return False
    if path.name in SKIP_NAMES:
        return False
    if path.suffix.lower() in SKIP_SUFFIX:
        return False
    if path.name.startswith(SKIP_PREFIX):
        return False
    parts = rel.parts
    if parts[0] in {"kb", "web"}:
        return True
    if parts[0] == "data" and len(parts) > 1 and parts[1] in {"extracted", "index"}:
        return True
    if len(parts) == 1 and path.name in KEEP_ROOT:
        return True
    return False


def main() -> None:
    files = [p for p in ROOT.rglob("*") if p.is_file() and keep(p)]
    files.sort(key=lambda p: p.as_posix())
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            zf.write(path, path.relative_to(ROOT).as_posix())
    print(f"已打包 {len(files)} 个文件 -> {OUT}")
    print("未包含：三册 PDF、.venv、密钥文件。对方只需安装 Python 后双击 启动知识库.bat。")


if __name__ == "__main__":
    main()
