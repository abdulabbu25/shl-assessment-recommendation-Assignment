import argparse
import json
from pathlib import Path
from typing import List

from app.retrieval.recommender import Recommender
from app.eval.metrics import recall_at_k


def load_train(path: Path):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rows.append(json.loads(line))
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", type=Path, required=True, help="Labeled train jsonl with fields: query, relevant_urls")
    ap.add_argument("--catalog", type=Path, default=Path("app/data/sample_catalog.json"))
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--pred_out", type=Path, default=None)
    args = ap.parse_args()

    rec = Recommender(data_path=args.catalog)
    data = load_train(args.train)

    scores: List[float] = []
    preds_dump = []
    for row in data:
        q = row["query"]
        rel = row.get("relevant_urls", [])
        items = rec.recommend(q, min_k=1, max_k=args.k)
        urls = [it["url"] for it in items]
        r = recall_at_k(rel, urls, args.k)
        scores.append(r)
        preds_dump.append({"query": q, "relevant_urls": rel, "predicted_urls": urls})

    mean_recall = sum(scores) / max(1, len(scores))
    print(f"Mean Recall@{args.k}: {mean_recall:.4f}")

    if args.pred_out:
        with open(args.pred_out, "w", encoding="utf-8") as f:
            for row in preds_dump:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"Wrote predictions to {args.pred_out}")
