# SHL Assessment Recommendation System

Python + FastAPI implementation of a retrieval-augmented recommendation engine for SHL **Individual Test Solutions**.

## Quickstart

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the API:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

4. Test endpoints:

- GET `/health` → `{"status":"healthy"}`  
- POST `/recommend` with body `{"query":"python developer who collaborates well"}`.

By default, the app uses a tiny sample catalog at `app/data/sample_catalog.json` to demonstrate the response format end‑to‑end. Replace it by running the crawler and building an index (instructions below).

## Project Structure

- `app/main.py` – FastAPI app with `/health` and `/recommend`.
- `app/data/` – Catalog JSON and artifacts.
- `app/crawl/shl_crawler.py` – Crawler for SHL catalog (individual test solutions only).
- `app/embeddings/provider.py` – Embedding providers (OpenAI/Gemini) with offline fallback.
- `app/store/vector_store.py` – FAISS/Chroma‑style index with portable fallback.
- `app/retrieval/recommender.py` – Retrieval, LLM re‑rank stub, and type balancing.
- `app/eval/metrics.py` – Mean Recall@10 and CLI.
- `scripts/` – Utilities to build index and generate CSV.

## Environment Variables

```
OPENAI_API_KEY=...      # optional
GEMINI_API_KEY=...      # optional
```

If no API keys are set, the system falls back to a deterministic local embedding for development.

## Building the Real Index

1. Crawl SHL and export `catalog.json` (individual test solutions only).
2. Build embeddings and vector store artifacts.
3. Start the API; the recommender will load the vector store automatically if present.

## Evaluation & Submission

- Evaluate Mean Recall@10 on provided train set with:

```bash
python -m app.eval.metrics --train data/train.jsonl --k 10
```

- Generate CSV for the unlabeled test set:

```bash
python scripts/generate_csv.py --queries data/test_unlabeled.jsonl --out submission.csv
```

This produces a two‑column CSV with headers `Query,Assessment_url` exactly as required.

## Notes

- No secrets are committed. Set keys via environment variables.
- FAISS is preferred; a portable fallback index ensures local dev works without external APIs.

