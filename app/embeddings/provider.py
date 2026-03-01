import os
from typing import List, Optional
import numpy as np


class EmbeddingsProvider:
    """
    Pluggable embeddings. Prefers OpenAI, then Gemini; otherwise uses a fast local fallback.
    The local fallback is a hashing-based embedding for deterministic dev without network.
    """

    def __init__(self, model: Optional[str] = None):
        self.model = model
        self._mode = "fallback"

        self._openai_client = None
        self._gemini = None

        # Allow forcing fallback via env
        force = os.getenv("EMBEDDINGS_MODE", "").lower() == "fallback"

        openai_key = os.getenv("OPENAI_API_KEY")
        gemini_key = os.getenv("GEMINI_API_KEY")

        if (not force) and openai_key:
            try:
                from openai import OpenAI  # type: ignore

                self._openai_client = OpenAI()
                self._mode = "openai"
                self.model = model or "text-embedding-3-large"
            except Exception:
                self._openai_client = None

        if (not force) and self._mode == "fallback" and gemini_key:
            try:
                import google.generativeai as genai  # type: ignore

                genai.configure(api_key=gemini_key)
                self._gemini = genai
                self._mode = "gemini"
                self.model = model or "text-embedding-004"
            except Exception:
                self._gemini = None

        if self._mode == "fallback":
            self.model = "hashing-512"

    def embed(self, texts: List[str]) -> np.ndarray:
        if self._mode == "openai":
            try:
                resp = self._openai_client.embeddings.create(model=self.model, input=texts)  # type: ignore
                vecs = [d.embedding for d in resp.data]  # type: ignore
                return np.array(vecs, dtype=np.float32)
            except Exception:
                self._mode = "fallback"

        if self._mode == "gemini":
            try:
                vecs = []
                for t in texts:
                    r = self._gemini.embed_content(model=self.model, content=t)  # type: ignore
                    vecs.append(r["embedding"])  # type: ignore
                return np.array(vecs, dtype=np.float32)
            except Exception:
                self._mode = "fallback"

        # Fallback: simple hashing trick into fixed dims
        dim = 512
        rng = np.random.default_rng(42)
        # fixed random projection for reproducibility
        proj = rng.standard_normal((dim, 2048)).astype(np.float32)

        def text_to_vec(text: str) -> np.ndarray:
            tokens = text.lower().split()
            counts = np.zeros(2048, dtype=np.float32)
            for tok in tokens:
                h = (hash(tok) % 2048 + 2048) % 2048
                counts[h] += 1.0
            vec = proj @ counts
            norm = np.linalg.norm(vec) + 1e-9
            return vec / norm

        arr = np.stack([text_to_vec(t) for t in texts], axis=0)
        return arr
