import json
from pathlib import Path
from typing import List, Tuple, Optional
import numpy as np


class VectorStore:
    """
    Minimal FAISS-like store with cosine similarity.
    Prefers faiss if installed; falls back to numpy search.
    """

    def __init__(self, dim: int):
        self.dim = dim
        self._index = None
        self._faiss = None
        try:
            import faiss  # type: ignore

            self._faiss = faiss
        except Exception:
            self._faiss = None
        self._vectors: Optional[np.ndarray] = None
        self._meta: List[dict] = []

    def add(self, vectors: np.ndarray, meta: List[dict]):
        assert vectors.shape[0] == len(meta), "Vectors and metadata length mismatch"
        # Normalize for cosine similarity
        norms = np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-9
        vectors = vectors / norms
        self._vectors = vectors if self._vectors is None else np.vstack([self._vectors, vectors])
        self._meta.extend(meta)

        if self._faiss is not None:
            if self._index is None:
                self._index = self._faiss.IndexFlatIP(self.dim)
            self._index.add(vectors.astype(np.float32))

    def search(self, query_vecs: np.ndarray, k: int) -> List[List[Tuple[int, float]]]:
        # Normalize query
        q = query_vecs / (np.linalg.norm(query_vecs, axis=1, keepdims=True) + 1e-9)
        if self._faiss is not None and self._index is not None:
            D, I = self._index.search(q.astype(np.float32), k)
            results: List[List[Tuple[int, float]]] = []
            for inds, scores in zip(I, D):
                results.append([(int(i), float(s)) for i, s in zip(inds, scores) if i != -1])
            return results

        # Fallback to numpy cosine search
        assert self._vectors is not None, "Index empty"
        sims = q @ self._vectors.T
        results: List[List[Tuple[int, float]]] = []
        for row in sims:
            idx = np.argpartition(-row, kth=min(k, len(row) - 1))[:k]
            best = sorted([(int(i), float(row[i])) for i in idx], key=lambda x: x[1], reverse=True)
            results.append(best)
        return results

    def size(self) -> int:
        return 0 if self._vectors is None else int(self._vectors.shape[0])

    def meta_at(self, i: int) -> dict:
        return self._meta[i]

    def save(self, out_dir: Path):
        out_dir.mkdir(parents=True, exist_ok=True)
        if self._vectors is None:
            raise ValueError("No vectors to save")
        np.save(out_dir / "vectors.npy", self._vectors)
        with open(out_dir / "meta.json", "w", encoding="utf-8") as f:
            json.dump(self._meta, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, in_dir: Path) -> "VectorStore":
        vectors = np.load(in_dir / "vectors.npy")
        with open(in_dir / "meta.json", "r", encoding="utf-8") as f:
            meta = json.load(f)
        store = cls(dim=int(vectors.shape[1]))
        store.add(vectors, meta)
        return store
