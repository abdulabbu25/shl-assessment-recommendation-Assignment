from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional
import os
import json
from pathlib import Path
from app.retrieval.recommender import Recommender
from fastapi.responses import FileResponse


class RecommendRequest(BaseModel):
    query: str = Field(..., min_length=1)


class Assessment(BaseModel):
    url: HttpUrl
    name: str
    adaptive_support: str
    description: str
    duration: int
    remote_support: str
    test_type: List[str]


class RecommendResponse(BaseModel):
    recommended_assessments: List[Assessment]


APP_ROOT = Path(__file__).resolve().parent
DATA_DIR = APP_ROOT / "data"
DEFAULT_CATALOG = DATA_DIR / "sample_catalog.json"
REAL_CATALOG = DATA_DIR / "catalog.json"


def _simple_retrieval(query: str, k: int = 7) -> List[dict]:
    """
    Very lightweight fallback retrieval over the local catalog.
    This is only for bootstrapping; the vector store pipeline will replace it.
    """
    if not DEFAULT_CATALOG.exists():
        return []
    with open(DEFAULT_CATALOG, "r", encoding="utf-8") as f:
        items = json.load(f)

    q = query.lower()
    scored = []
    for it in items:
        text = " ".join(
            [
                it.get("name", ""),
                it.get("description", ""),
                " ".join(it.get("test_type", [])),
            ]
        ).lower()
        overlap = len(set(q.split()) & set(text.split()))
        # prefer items with any overlap; break ties by description length
        score = overlap * 1000 - len(text)
        scored.append((score, it))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [it for _, it in scored[:k]]


def create_app() -> FastAPI:
    app = FastAPI(title="SHL Assessment Recommender", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health():
        return {"status": "healthy"}

    @app.get("/")
    def home():
        ui = APP_ROOT / "ui" / "index.html"
        if ui.exists():
            return FileResponse(str(ui))
        return {"message": "UI not found"}

    # Initialize recommender with real catalog if present, otherwise sample
    catalog_path = REAL_CATALOG if REAL_CATALOG.exists() else (DEFAULT_CATALOG if DEFAULT_CATALOG.exists() else None)
    recommender: Optional[Recommender] = None
    if catalog_path:
        try:
            recommender = Recommender(data_path=catalog_path)
        except Exception:
            recommender = None

    @app.post("/recommend", response_model=RecommendResponse)
    def recommend(body: RecommendRequest):
        try:
            if recommender is not None:
                results = recommender.recommend(body.query, min_k=5, max_k=10)
            else:
                results = _simple_retrieval(body.query, k=7)
            # Ensure field types and required shape
            normalized = []
            for r in results:
                try:
                    a = Assessment(
                        url=r["url"],
                        name=r["name"],
                        adaptive_support=r.get("adaptive_support", "No"),
                        description=r.get("description", ""),
                        duration=int(r.get("duration", 0)),
                        remote_support=r.get("remote_support", "No"),
                        test_type=r.get("test_type", []),
                    )
                    normalized.append(a)
                except Exception:
                    # Skip malformed
                    continue
            return RecommendResponse(recommended_assessments=normalized)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/recommend", response_model=RecommendResponse)
    def recommend_get(query: str):
        try:
            if recommender is not None:
                results = recommender.recommend(query, min_k=5, max_k=10)
            else:
                results = _simple_retrieval(query, k=7)
            normalized = []
            for r in results:
                try:
                    a = Assessment(
                        url=r["url"],
                        name=r["name"],
                        adaptive_support=r.get("adaptive_support", "No"),
                        description=r.get("description", ""),
                        duration=int(r.get("duration", 0)),
                        remote_support=r.get("remote_support", "No"),
                        test_type=r.get("test_type", []),
                    )
                    normalized.append(a)
                except Exception:
                    continue
            return RecommendResponse(recommended_assessments=normalized)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


app = create_app()

