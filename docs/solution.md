# SHL Assessment Recommendation System — Architecture & Optimization (2 Pages)

## Overview
This system recommends relevant **SHL Individual Test Solutions** given a natural‑language query or JD URL text. It integrates a modular pipeline: data ingestion (crawler) → cleaning → embeddings → vector store retrieval → LLM or deterministic re‑ranking → diversity balancing by `test_type` → API/UI.

## Data Ingestion
- Source: SHL product catalog (individual solutions only; pre‑packaged job solutions are excluded).
- Crawler: `app/crawl/shl_crawler.py` scrapes listing pages, filters out pre‑packaged solutions, extracts fields:
  - `name`, `url`, `description`, `duration`, `adaptive_support`, `remote_support`, `test_type`.
- Output: `catalog.json` → used to build the index.

## Embeddings & Vector Store
- Embeddings Provider: `app/embeddings/provider.py`
  - Prefers OpenAI `text-embedding-3-large`; fallback: Gemini `text-embedding-004`.
  - Offline deterministic hashing‑based embedding for dev without network keys.
- Vector Store: `app/store/vector_store.py`
  - FAISS inner‑product index if available; fallback to normalized NumPy cosine search.
  - Artifacts stored under `app/data/store` (`vectors.npy`, `meta.json`).

## Retrieval and Ranking
- Retriever: `Recommender.retrieve` embeds query and searches top‑K (default 40).
- Re‑ranking:
  - Optional LLM re‑rank (`Recommender.rerank_llm`) if `OPENAI_API_KEY`/`GEMINI_API_KEY` is set, via a lightweight JSON‑scoring prompt.
  - Deterministic fallback (`Recommender.rerank`) uses query‑term overlap for a safe, explainable baseline.
- Diversity Balancing: `balance_by_type` performs category‑round‑robin over `test_type` to deliver a mix of hard/soft‑skill assessments.

## API & UI
- FastAPI: `app/main.py`
  - `GET /health` → `{"status":"healthy"}`.
  - `POST /recommend` → JSON with `recommended_assessments` (5–10 items) with exact field schema.
- UI: Minimal client in `app/ui/index.html` for quick manual testing.
- Dockerfile and `render.yaml` included for straightforward deployment.

## Evaluation
- Metric: **Mean Recall@10**.
- Tools:
  - `app/eval/metrics.py` — R@K and MR@K computation.
  - `scripts/eval_train.py` — Loads labeled train set (with `relevant_urls`), runs pipeline, prints MR@10. Optionally writes predictions JSONL.
- Process:
  1) Build the full catalog (≥377 items).
  2) Build embeddings & index.
  3) Run `eval_train.py` and record Mean Recall@10.
  4) Iterate: adjust retriever K, switch to OpenAI/Gemini embeddings, enable LLM re‑rank.

## Prediction CSV (Submission)
- Script: `scripts/generate_csv.py`
- Input: unlabeled test queries (`.jsonl` or `.txt`).
- Output: 2‑column CSV with headers `Query,Assessment_url` — one row per recommendation. Format matches the assignment’s Appendix 3.

## Optimization Summary
- Retrieval K=40 helps recall without over‑fetching noise.
- FAISS improves speed; when unavailable, NumPy fallback keeps the flow working.
- LLM re‑rank (small/cheap models) improves ordering; falls back to deterministic scoring if no key.
- Round‑robin across `test_type` enforces balanced coverage (e.g., “Knowledge & Skills” + “Personality & Behavior”).

## Security & Reliability
- No secrets in code; API keys read from environment variables.
- Deterministic local embedding ensures development works without external services.
- Validation: smoke test at `scripts/smoke_test.py` verifies `/health` and `/recommend`.

## Deployment
- Dockerized app: `docker build -t shl-recommender .` then `docker run -p 8000:8000 shl-recommender`.
- Render deployment: use `render.yaml`, set `OPENAI_API_KEY`/`GEMINI_API_KEY` in the dashboard.
- Health check: `/health`. UI included at `/`.

## How to Reproduce
1. Crawl: `python -m app.crawl.shl_crawler` → `catalog.json` (≥377).
2. Index: `python scripts/build_index.py --catalog app/data/catalog.json`.
3. Serve: `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
4. Evaluate: `python scripts/eval_train.py --train data/train.jsonl --catalog app/data/catalog.json --k 10`.
5. Generate CSV: `python scripts/generate_csv.py --queries data/test_unlabeled.jsonl --catalog app/data/catalog.json --out submission.csv --k 10`.

## Notes for Reviewers
- The system adheres to the required API schema, computes Mean Recall@10, and produces the exact CSV format.
- The design is modular and easily switchable between local and cloud‑backed embeddings.

