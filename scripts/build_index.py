from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))
import argparse
from app.retrieval.recommender import Recommender

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", type=Path, required=True, help="Path to catalog JSON")
    ap.add_argument("--store", type=Path, default=None, help="Directory to save index")
    args = ap.parse_args()

    rec = Recommender(data_path=args.catalog, store_dir=args.store)
    print(f"Indexed {len(rec.items)} items into {rec.store_dir}")
