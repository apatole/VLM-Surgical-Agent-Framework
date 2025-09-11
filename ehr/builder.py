import json
import os
from typing import List, Dict, Any, Iterable, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer

try:
    import faiss  # type: ignore
except Exception as e:  # pragma: no cover
    faiss = None

import tiktoken


def _iter_files(input_path: str) -> Iterable[str]:
    if os.path.isdir(input_path):
        for root, _, files in os.walk(input_path):
            for name in files:
                if name.lower().endswith((".txt", ".md", ".json")):
                    yield os.path.join(root, name)
    else:
        yield input_path


def _load_text_from_file(path: str) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Return a list of (text, metadata) pairs extracted from supported file types.
    For JSON, attempt to collect string values recursively.
    """
    ext = os.path.splitext(path)[1].lower()
    if ext in (".txt", ".md"):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return [(f.read(), {"source": path})]
    if ext == ".json":
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            data = json.load(f)
        texts: List[str] = []
        def collect(v: Any):
            if isinstance(v, str):
                texts.append(v)
            elif isinstance(v, dict):
                for vv in v.values():
                    collect(vv)
            elif isinstance(v, list):
                for vv in v:
                    collect(vv)
        collect(data)
        return [(t, {"source": path}) for t in texts if t and t.strip()]
    return []


def _chunk_text(text: str, *, chunk_tokens: int, overlap_tokens: int, tokenizer) -> List[str]:
    """
    Token-based chunking using tiktoken. Keeps rough token sizes for retrieval.
    """
    ids = tokenizer.encode(text)
    chunks: List[str] = []
    start = 0
    while start < len(ids):
        end = min(start + chunk_tokens, len(ids))
        chunk_ids = ids[start:end]
        chunk_text = tokenizer.decode(chunk_ids)
        chunks.append(chunk_text)
        if end == len(ids):
            break
        start = end - overlap_tokens
        if start < 0:
            start = 0
    return chunks


def build_ehr_index(
    input_path: str,
    output_dir: str,
    *,
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    chunk_tokens: int = 256,
    overlap_tokens: int = 32,
) -> str:
    """
    Build a FAISS index for EHR retrieval from text/JSON files.

    Returns the output directory used.
    """
    if faiss is None:
        raise RuntimeError("faiss is not installed. Please install faiss-cpu.")

    os.makedirs(output_dir, exist_ok=True)
    tokenizer = tiktoken.get_encoding("cl100k_base")
    embedder = SentenceTransformer(embedding_model_name)

    texts_meta: List[Dict[str, Any]] = []
    for fp in _iter_files(input_path):
        for text, meta in _load_text_from_file(fp):
            if not text or not text.strip():
                continue
            for i, chunk in enumerate(_chunk_text(text, chunk_tokens=chunk_tokens, overlap_tokens=overlap_tokens, tokenizer=tokenizer)):
                texts_meta.append({
                    "text": chunk,
                    "metadata": {**meta, "chunk_index": i}
                })

    if not texts_meta:
        raise ValueError(f"No text extracted from: {input_path}")

    # Embed
    embeddings = embedder.encode(
        [x["text"] for x in texts_meta], batch_size=64, show_progress_bar=False, normalize_embeddings=True
    )
    embeddings = np.asarray(embeddings, dtype="float32")

    # Build FAISS index (cosine via inner product on normalized vectors)
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)

    # Persist
    faiss_path = os.path.join(output_dir, "faiss.index")
    faiss.write_index(index, faiss_path)

    with open(os.path.join(output_dir, "docstore.json"), "w") as f:
        json.dump(texts_meta, f, ensure_ascii=False)

    with open(os.path.join(output_dir, "meta.json"), "w") as f:
        json.dump(
            {
                "embedding_model_name": embedding_model_name,
                "dims": int(dim),
                "chunk_tokens": chunk_tokens,
                "overlap_tokens": overlap_tokens,
            },
            f,
            indent=2,
        )

    return output_dir

