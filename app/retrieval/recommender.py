from pathlib import Path
from typing import List, Dict, Any, Optional
import os
import json
import numpy as np

from app.embeddings.provider import EmbeddingsProvider
from app.store.vector_store import VectorStore


class Recommender:
    def __init__(self, data_path: Path, store_dir: Optional[Path] = None):
        self.data_path = data_path
        self.store_dir = store_dir or (data_path.parent / "store")
        self.items: List[Dict[str, Any]] = self._load_items()
        self.embedder = EmbeddingsProvider()
        self.vs: Optional[VectorStore] = None
        self._ensure_index()

    def _load_items(self) -> List[Dict[str, Any]]:
        with open(self.data_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _ensure_index(self):
        # Try to load existing
        vec_path = self.store_dir / "vectors.npy"
        meta_path = self.store_dir / "meta.json"
        if vec_path.exists() and meta_path.exists():
            self.vs = VectorStore.load(self.store_dir)
            return

        texts = [
            " ".join(
                [
                    it.get("name", ""),
                    it.get("description", ""),
                    " ".join(it.get("test_type", [])),
                ]
            )
            for it in self.items
        ]
        vecs = self.embedder.embed(texts)
        self.vs = VectorStore(dim=int(vecs.shape[1]))
        self.vs.add(vecs, self.items)
        self.vs.save(self.store_dir)

    def retrieve(self, query: str, k: int = 20) -> List[Dict[str, Any]]:
        qv = self.embedder.embed([query])
        assert self.vs is not None
        hits = self.vs.search(qv, k)
        idxs = [i for i, _ in hits[0]]
        return [self.vs.meta_at(i) for i in idxs]

    def rerank(self, query: str, candidates: List[Dict[str, Any]], top_n: int = 10) -> List[Dict[str, Any]]:
        # Lightweight, deterministic rerank using query-term overlap as a stand-in for LLM
        q = set(query.lower().split())
        def score(item):
            text = " ".join(
                [item.get("name", ""), item.get("description", ""), " ".join(item.get("test_type", []))]
            ).lower()
            return len(q & set(text.split()))
        scored = sorted(candidates, key=score, reverse=True)
        return scored[:top_n]

    def rerank_llm(self, query: str, candidates: List[Dict[str, Any]], top_n: int = 10) -> Optional[List[Dict[str, Any]]]:
        """
        Optional LLM-based reranker if API keys are available. Returns None if not configured.
        Uses a simple scoring prompt and parses numeric relevance.
        """
        use_openai = bool(os.getenv("OPENAI_API_KEY"))
        use_gemini = bool(os.getenv("GEMINI_API_KEY"))
        if not (use_openai or use_gemini):
            return None

        items = candidates[: min(20, len(candidates))]
        prompt = (
            "You are a ranking assistant. Score each assessment for relevance to the query from 0 to 10.\n"
            "Return a JSON list of objects: [{\"i\": index, \"score\": number}].\n"
            f"Query: {query}\n\n"
            "Assessments:\n"
        )
        for i, it in enumerate(items):
            line = f"{i}. {it.get('name','')} | {', '.join(it.get('test_type', []))} | {it.get('description','')}\n"
            prompt += line

        try:
            if use_openai:
                from openai import OpenAI  # type: ignore
                client = OpenAI()
                resp = client.chat.completions.create(
                    model=os.environ.get("RERANK_MODEL", "gpt-4o-mini"),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                )
                txt = resp.choices[0].message.content  # type: ignore
            else:
                import google.generativeai as genai  # type: ignore
                model = os.environ.get("RERANK_MODEL", "gemini-1.5-flash")
                gen = genai.GenerativeModel(model)  # type: ignore
                r = gen.generate_content(prompt)  # type: ignore
                txt = r.text
            data = json.loads(txt)
            # Build score map and sort
            score_map = {int(obj["i"]): float(obj["score"]) for obj in data if "i" in obj and "score" in obj}
            scored = sorted([(score_map.get(i, 0.0), i) for i in range(len(items))], reverse=True)
            out = [items[i] for _, i in scored[:top_n]]
            return out
        except Exception:
            return None

    def balance_by_type(self, items: List[Dict[str, Any]], limit: int = 7) -> List[Dict[str, Any]]:
        # Ensure mix of test_type categories when possible
        buckets = {}
        for it in items:
            types = it.get("test_type", []) or ["Unknown"]
            key = types[0]
            buckets.setdefault(key, []).append(it)
        out: List[Dict[str, Any]] = []
        # round-robin
        keys = list(buckets.keys())
        i = 0
        while len(out) < min(limit, len(items)) and any(buckets.values()):
            key = keys[i % len(keys)]
            if buckets[key]:
                out.append(buckets[key].pop(0))
            i += 1
            if i > 1000:  # safety
                break
        return out[:limit]

    def recommend(self, query: str, min_k: int = 5, max_k: int = 10) -> List[Dict[str, Any]]:
        cands = self.retrieve(query, k=40)
        reranked = self.rerank_llm(query, cands, top_n=max_k * 2) or self.rerank(query, cands, top_n=max_k * 2)
        balanced = self.balance_by_type(reranked, limit=max_k)
        if len(balanced) < min_k:
            balanced = reranked[:max(min_k, len(reranked))]
        return balanced[:max_k]
