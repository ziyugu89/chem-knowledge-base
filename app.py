from __future__ import annotations

import json
import os
import webbrowser
from threading import Lock, Timer

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from kb.config import APP_HOST, APP_PORT, PROVIDERS, WEB_DIR
from kb.ingest_extra import delete_extra, save_text, save_upload
from kb.rag import stream_answer
from kb.refine import refine_passage, reset_page_cache, sources_from_hits
from kb.retrieve import extract_ready, load_or_build

load_dotenv()

app = FastAPI(title="氟化工生产技术知识库")
app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")

INDEX = None
INDEX_LOCK = Lock()


def get_index():
    global INDEX
    with INDEX_LOCK:
        if INDEX is None:
            INDEX = load_or_build()
        return INDEX


def reload_index():
    global INDEX
    with INDEX_LOCK:
        reset_page_cache()
        INDEX = load_or_build(force=True)
        return INDEX


class QueryBody(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    top_k: int = 4
    provider: str = "deepseek"
    model: str = ""
    base_url: str = ""
    api_key: str = ""


class ExtraBody(BaseModel):
    title: str = ""
    text: str = Field(min_length=1, max_length=200000)


@app.get("/")
def home():
    return FileResponse(WEB_DIR / "templates" / "index.html")


@app.get("/api/status")
def status():
    ready = extract_ready()
    index = None
    chunks = 0
    try:
        index = get_index()
        chunks = len(index.chunks)
    except FileNotFoundError:
        pass
    return {
        "books": ready,
        "chunks": chunks,
        "vector_dim": getattr(index, "vector_dim", 0) if index else 0,
        "retriever": "TF-IDF向量 + BM25 混合检索",
        "ready": chunks > 0,
        "extra": ready.get("extra") or {"docs": 0, "items": []},
        "providers": {
            k: {"name": v["name"], "model": v["model"], "base_url": v["base_url"], "hint": v["hint"]}
            for k, v in PROVIDERS.items()
        },
    }


@app.post("/api/rebuild")
def rebuild():
    return _index_payload(reload_index())


def _index_payload(index):
    ready = extract_ready()
    return {
        "ok": True,
        "chunks": len(index.chunks),
        "vector_dim": getattr(index, "vector_dim", 0),
        "retriever": "TF-IDF向量 + BM25 混合检索",
        "books": ready,
        "extra": ready.get("extra") or {"docs": 0, "items": []},
    }


@app.get("/api/extra")
def extra_list():
    ready = extract_ready()
    return ready.get("extra") or {"docs": 0, "items": []}


@app.post("/api/extra")
def extra_add(body: ExtraBody):
    try:
        doc = save_text(body.title, body.text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    index = reload_index()
    payload = _index_payload(index)
    payload["doc"] = doc
    return payload


@app.post("/api/extra/upload")
async def extra_upload(file: UploadFile = File(...), title: str = Form("")):
    data = await file.read()
    try:
        doc = save_upload(file.filename or "upload.txt", data, title=title)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    index = reload_index()
    payload = _index_payload(index)
    payload["doc"] = doc
    return payload


@app.delete("/api/extra/{doc_id}")
def extra_delete(doc_id: str):
    if not delete_extra(doc_id):
        raise HTTPException(status_code=404, detail="没有这条补充资料")
    index = reload_index()
    return _index_payload(index)


@app.post("/api/search")
def search(body: QueryBody):
    index = get_index()
    hits = index.search(body.question, top_k=body.top_k)
    passage = refine_passage(body.question, hits)
    return {
        "answer": passage["answer"],
        "hits": passage.get("hits") or sources_from_hits(hits, body.question),
    }


@app.post("/api/chat")
def chat(body: QueryBody):
    index = get_index()
    hits = index.search(body.question, top_k=body.top_k)
    settings = {
        "provider": body.provider,
        "model": body.model,
        "base_url": body.base_url,
        "api_key": body.api_key or os.getenv("LLM_API_KEY", ""),
    }

    passage = refine_passage(body.question, hits)
    source_items = passage.get("hits") or sources_from_hits(hits, body.question)

    def generate():
        yield f"data: {json.dumps({'type': 'sources', 'items': source_items}, ensure_ascii=False)}\n\n"
        try:
            if not settings["api_key"]:
                yield f"data: {json.dumps({'type': 'token', 'text': passage['answer']}, ensure_ascii=False)}\n\n"
            else:
                for token in stream_answer(body.question, hits, settings):
                    yield f"data: {json.dumps({'type': 'token', 'text': token}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'token', 'text': passage['answer']}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'error', 'text': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


def main() -> None:
    import uvicorn

    url = f"http://{APP_HOST}:{APP_PORT}"
    print(f"\n氟化工生产技术知识库已启动：{url}\n浏览器将自动打开，关闭本窗口即停止服务。\n")
    Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=APP_HOST, port=APP_PORT, log_level="info")


if __name__ == "__main__":
    main()
