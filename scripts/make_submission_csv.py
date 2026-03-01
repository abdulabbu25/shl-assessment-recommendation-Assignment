from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))
import json
import csv
import os
from app.retrieval.recommender import Recommender

DEFAULT_QUERIES = [
    "I am hiring for Java developers who can also collaborate effectively with my business teams.",
    "Looking to hire mid-level professionals who are proficient in Python, SQL and JavaScript.",
    "Recommend assessments for analysts focusing on Cognitive and Personality tests."
]

def load_queries() -> list[str]:
    p1 = Path("data/test_unlabeled.jsonl")
    p2 = Path("data/test_unlabeled.txt")
    if p1.exists():
        out = []
        for line in p1.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            out.append(obj["query"])
        return out
    if p2.exists():
        return [l.strip() for l in p2.read_text(encoding="utf-8").splitlines() if l.strip()]
    return DEFAULT_QUERIES

if __name__ == "__main__":
    os.environ["EMBEDDINGS_MODE"] = "fallback"
    catalog = Path("app/data/catalog.json") if Path("app/data/catalog.json").exists() else Path("app/data/sample_catalog.json")
    rec = Recommender(data_path=catalog)
    queries = load_queries()
    out_path = Path("abdullah_s.csv")
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Query", "Assessment_url"])
        for q in queries:
            items = rec.recommend(q, min_k=3, max_k=10)
            for it in items:
                w.writerow([q, it["url"]])
    print(f"Wrote {out_path.resolve()} with {len(queries)} queries.")
