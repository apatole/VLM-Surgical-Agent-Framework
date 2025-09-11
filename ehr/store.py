import json
import os
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any

import numpy as np
from sentence_transformers import SentenceTransformer

try:
    import faiss  # type: ignore
except Exception as e:  # pragma: no cover
    faiss = None


@dataclass
class RetrievedChunk:
    text: str
    score: float
    metadata: Dict[str, Any]


class EHRVectorStore:
    """
    Thin wrapper around a FAISS index + parallel docstore.

    Directory layout:
      index_dir/
        faiss.index          – binary FAISS index
        docstore.json        – list[ {"text": str, "metadata": {...}} ] in same order
        meta.json            – config info (embedding model, dims, etc.)
    """

    def __init__(self, index_dir: str, model_name: str | None = None):
        if faiss is None:
            raise RuntimeError("faiss is not installed. Please install faiss-cpu.")
        self.index_dir = index_dir
        meta_path = os.path.join(index_dir, "meta.json")
        with open(meta_path, "r") as f:
            meta = json.load(f)

        self.model_name = model_name or meta.get("embedding_model_name") or "sentence-transformers/all-MiniLM-L6-v2"
        self.embedder = SentenceTransformer(self.model_name)

        # Load FAISS
        faiss_path = os.path.join(index_dir, "faiss.index")
        self.index = faiss.read_index(faiss_path)

        # Load docstore
        docstore_path = os.path.join(index_dir, "docstore.json")
        with open(docstore_path, "r") as f:
            self.docstore: List[Dict[str, Any]] = json.load(f)

        if self.index.ntotal != len(self.docstore):  # pragma: no cover
            raise ValueError("FAISS index size and docstore length mismatch")

    @classmethod
    def from_dir(cls, index_dir: str, model_name: str | None = None) -> "EHRVectorStore":
        return cls(index_dir=index_dir, model_name=model_name)

    def embed(self, texts: List[str]) -> np.ndarray:
        vecs = self.embedder.encode(texts, batch_size=64, show_progress_bar=False, normalize_embeddings=True)
        return np.asarray(vecs, dtype="float32")

    def query(self, query_text: str, top_k: int = 5) -> List[RetrievedChunk]:
        q = self.embed([query_text])
        scores, idxs = self.index.search(q, top_k)
        results: List[RetrievedChunk] = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx == -1:
                continue
            entry = self.docstore[idx]
            results.append(
                RetrievedChunk(text=entry["text"], score=float(score), metadata=entry.get("metadata", {}))
            )
        return results

