import argparse
import json
from pathlib import Path
from typing import List, Dict


def recall_at_k(relevant_urls: List[str], recommended_urls: List[str], k: int) -> float:
    topk = set(recommended_urls[:k])
    rel = set(relevant_urls)
    if not rel:
        return 0.0
    return len(rel & topk) / len(rel)


def mean_recall_at_k(train_path: Path, k: int) -> float:
    with open(train_path, "r", encoding="utf-8") as f:
        lines = [json.loads(l) for l in f if l.strip()]
    scores = []
    for row in lines:
        query = row["query"]
        relevant = row["relevant_urls"]
        # placeholder: assumes predictions are precomputed in row for offline eval
        preds = row.get("predicted_urls", [])
        scores.append(recall_at_k(relevant, preds, k))
    return sum(scores) / max(1, len(scores))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", required=True, type=Path, help="Path to labeled train jsonl")
    ap.add_argument("--k", default=10, type=int)
    args = ap.parse_args()

    score = mean_recall_at_k(args.train, args.k)
    print(f"Mean Recall@{args.k}: {score:.4f}")

