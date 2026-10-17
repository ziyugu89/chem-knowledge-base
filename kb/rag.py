from __future__ import annotations

from collections.abc import Iterator

from openai import OpenAI

from kb.config import PROVIDERS
from kb.refine import refine_passage
from kb.retrieve import Hit

SYSTEM_PROMPT = """你是《氟化工生产技术》（胡伟主编）的讲解员。根据提供的教材摘录回答问题。

写作要求：
- 先用两三句直接给出结论，再按需要分成 2～4 个小标题展开。
- 写成连贯说明文，每个小标题下用完整段落，不要编号堆砌、不要复述资料清单。
- 同一事实只说一次。删掉与问题无关的边角内容（目录、页码、编者名单等）。
- 只使用摘录里出现的信息，不要编造数据或工艺细节。
- 全文大约 350～700 字。最后单独一行：出处：……
- 简体中文。涉及危害时只作原则性提示，不写可操作的危险步骤。
"""


def compose_excerpt(question: str, hits: list[Hit]) -> str:
    packed = refine_passage(question, hits)
    lines = [packed["answer"]]
    extras = []
    for item in packed.get("hits") or []:
        extras.append(f"{item.get('cite')}\n{item.get('snippet')}")
    if extras:
        lines.append("\n\n【检索片段】\n" + "\n\n".join(extras[:3]))
    return "\n".join(lines)


def _format_context(hits: list[Hit], question: str = "") -> str:
    return compose_excerpt(question, hits)


def build_messages(question: str, hits: list[Hit]) -> list[dict]:
    context = _format_context(hits, question) if hits else "（没有检索到相关段落）"
    user = (
        f"问题：{question}\n\n"
        f"【教材摘录】\n{context}\n\n"
        "请把上述摘录整理成一篇连贯回答，直接针对问题，不要逐段复述。"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def resolve_provider(settings: dict) -> tuple[str, str, str]:
    provider = (settings.get("provider") or "deepseek").lower()
    meta = PROVIDERS.get(provider, PROVIDERS["deepseek"])
    base_url = (settings.get("base_url") or meta["base_url"]).strip()
    model = (settings.get("model") or meta["model"]).strip()
    api_key = (settings.get("api_key") or "").strip()
    if provider == "ollama" and not api_key:
        api_key = "ollama"
    return base_url, model, api_key


def stream_answer(question: str, hits: list[Hit], settings: dict) -> Iterator[str]:
    _base_url, _model, api_key = resolve_provider(settings)
    if not api_key:
        yield compose_excerpt(question, hits)
        return
    client = OpenAI(api_key=api_key, base_url=_base_url)
    stream = client.chat.completions.create(
        model=_model,
        messages=build_messages(question, hits),
        temperature=0.25,
        stream=True,
    )
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta and delta.content:
            yield delta.content
