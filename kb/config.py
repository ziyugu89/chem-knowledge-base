from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"
DATA_DIR = ROOT / "data"
EXTRACT_DIR = DATA_DIR / "extracted"
EXTRA_DIR = EXTRACT_DIR / "extra"
INDEX_DIR = DATA_DIR / "index"
WEB_DIR = ROOT / "web"

for _p in (DOCS_DIR, EXTRACT_DIR, EXTRA_DIR, INDEX_DIR, WEB_DIR):
    _p.mkdir(parents=True, exist_ok=True)

BOOK_META = {
    "上": {
        "label": "上册 · 无机氟化工",
        "title": "氟化工生产技术（上）",
        "focus": "概述、萤石资源、氢氟酸、无机氟化盐、精细无机氟化工",
        "filename_key": "上",
    },
    "中": {
        "label": "中册 · 有机氟化工",
        "title": "氟化工生产技术（中）",
        "focus": "含氟烃及替代品、含氟医药农药染料、有机氟中间体、含氟表面活性剂与整理剂",
        "filename_key": "中",
    },
    "下": {
        "label": "下册 · 含氟聚合物",
        "title": "氟化工生产技术（下）",
        "focus": "聚四氟乙烯、可熔性氟树脂、氟橡胶、氟涂料、产业展望",
        "filename_key": "下",
    },
}

PROVIDERS = {
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "hint": "https://platform.deepseek.com 创建 API Key",
    },
    "qwen": {
        "name": "通义千问",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "hint": "阿里云百炼 / DashScope API Key",
    },
    "moonshot": {
        "name": "Kimi (月之暗面)",
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-auto",
        "hint": "https://platform.moonshot.cn",
    },
    "siliconflow": {
        "name": "硅基流动",
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "Qwen/Qwen2.5-72B-Instruct",
        "hint": "https://siliconflow.cn 兼容 OpenAI 的模型",
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "hint": "官方 OpenAI API Key",
    },
    "ollama": {
        "name": "本地 Ollama",
        "base_url": "http://127.0.0.1:11434/v1",
        "model": "qwen2.5:7b",
        "hint": "需本机已启动 Ollama，API Key 可填 ollama",
    },
}

APP_HOST = "127.0.0.1"
APP_PORT = 8772
INDEX_FILE = INDEX_DIR / "kb.pkl"
INDEX_VERSION = 5
CHUNK_SIZE = 720
CHUNK_OVERLAP = 70
TOP_K = 4
CANDIDATES = 40
