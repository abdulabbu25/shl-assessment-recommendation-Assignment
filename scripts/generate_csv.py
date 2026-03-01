import argparse
import csv
import json
from pathlib import Path
from app.retrieval.recommender import Recommender


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queries", type=Path, required=True, help="Path to unlabeled test set (jsonl or txt)")
    ap.add_argument("--catalog", type=Path, default=Path("app/data/sample_catalog.json"))
    ap.add_argument("--out", type=Path, required=True, help="Output CSV path")
    ap.add_argument("--k", type=int, default=5)
    args = ap.parse_args()

    rec = Recommender(data_path=args.catalog)

    queries = []
    if args.queries.suffix.lower() == ".jsonl":
        with open(args.queries, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                obj = json.loads(line)
                queries.append(obj["query"])
    else:
        with open(args.queries, "r", encoding="utf-8") as f:
            for line in f:
                q = line.strip()
                if q:
                    queries.append(q)

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Query", "Assessment_url"])
        for q in queries:
            items = rec.recommend(q, min_k=1, max_k=args.k)
            for it in items:
                w.writerow([q, it["url"]])

    print(f"Wrote CSV to {args.out}")


if __name__ == "__main__":
    main()

