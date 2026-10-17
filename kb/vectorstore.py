from __future__ import annotations

import json
from collections import Counter

import numpy as np

from kb.config import INDEX_DIR

VECTOR_FILE = INDEX_DIR / "vectors.npz"
VOCAB_FILE = INDEX_DIR / "vocab.json"
VOCAB_SIZE = 5000


def build_tfidf_matrix(docs: list[list[str]]) -> tuple[list[str], np.ndarray, np.ndarray]:
    df: Counter[str] = Counter()
    tfs: list[Counter[str]] = []
    for toks in docs:
        tf = Counter(toks)
        tfs.append(tf)
        df.update(tf.keys())
    vocab = [w for w, _n in df.most_common(VOCAB_SIZE)]
    index = {w: i for i, w in enumerate(vocab)}
    n_docs = max(len(docs), 1)
    idf = np.array([np.log((n_docs + 1) / (df[w] + 1)) + 1.0 for w in vocab], dtype=np.float32)
    mat = np.zeros((len(docs), len(vocab)), dtype=np.float32)
    for i, tf in enumerate(tfs):
        for w, c in tf.items():
            j = index.get(w)
            if j is not None:
                mat[i, j] = float(c)
        mat[i] *= idf
        norm = float(np.linalg.norm(mat[i]))
        if norm > 0:
            mat[i] /= norm
    return vocab, idf, mat


def encode(tokens: list[str], vocab: list[str], idf: np.ndarray) -> np.ndarray:
    index = {w: i for i, w in enumerate(vocab)}
    vec = np.zeros(len(vocab), dtype=np.float32)
    for w, c in Counter(tokens).items():
        j = index.get(w)
        if j is not None:
            vec[j] = float(c) * float(idf[j])
    norm = float(np.linalg.norm(vec))
    if norm > 0:
        vec /= norm
    return vec


def save_vectors(vocab: list[str], idf: np.ndarray, matrix: np.ndarray) -> None:
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(VECTOR_FILE, idf=idf, matrix=matrix)
    VOCAB_FILE.write_text(json.dumps(vocab, ensure_ascii=False), encoding="utf-8")


def load_vectors() -> tuple[list[str], np.ndarray, np.ndarray] | None:
    if not VECTOR_FILE.exists() or not VOCAB_FILE.exists():
        return None
    vocab = json.loads(VOCAB_FILE.read_text(encoding="utf-8"))
    data = np.load(VECTOR_FILE)
    return vocab, data["idf"], data["matrix"]


def cosine_scores(matrix: np.ndarray, query_vec: np.ndarray) -> np.ndarray:
    return matrix @ query_vec
