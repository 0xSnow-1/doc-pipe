import json
from pathlib import Path

from src.artifacts import atomic_write_text
from src.data import build_split, download_cuad, load_cuad, split_to_dict

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    cache_dir = ROOT / "data" / "cache"
    path = download_cuad(cache_dir)
    dataset = load_cuad(path)
    split = build_split(dataset)
    atomic_write_text(
        ROOT / "data" / "split.json",
        json.dumps(split_to_dict(split), indent=2) + "\n",
    )
    print(
        f"wrote {ROOT / 'data' / 'split.json'} with {len(split.eval)} eval and {len(split.dev)} dev"
    )


if __name__ == "__main__":
    main()
