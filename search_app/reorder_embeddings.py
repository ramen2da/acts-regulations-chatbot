import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHUNKS_PATH = os.path.join(BASE_DIR, "chunks.jsonl")
SHARD_PATH = os.path.join(BASE_DIR, "..", "docs", "data", "embeddings", "규정집.json")


def key_of(c):
    return (c["regulation"], c["source_file"], c["article_no"], c["text"])


def main():
    with open(SHARD_PATH, encoding="utf-8") as f:
        embedded = json.load(f)
    print(f"Loaded {len(embedded)} embedded chunks")

    lookup = {}
    for c in embedded:
        lookup[key_of(c)] = c

    with open(CHUNKS_PATH, encoding="utf-8") as f:
        new_order = [json.loads(line) for line in f]
    print(f"Loaded {len(new_order)} chunks in new order")

    reordered = []
    missing = []
    for c in new_order:
        k = key_of(c)
        match = lookup.get(k)
        if match is None:
            missing.append(k)
            continue
        reordered.append(match)

    print(f"Matched {len(reordered)} / {len(new_order)}; missing {len(missing)}")
    if missing:
        for m in missing[:10]:
            print("  MISSING:", m[0], m[2])
        raise SystemExit("Aborting: some chunks have no matching embedding; re-run embed.py instead.")

    for idx, c in enumerate(reordered):
        c["id"] = idx

    with open(SHARD_PATH, "w", encoding="utf-8") as f:
        json.dump(reordered, f, ensure_ascii=False)
    print(f"Wrote reordered shard: {SHARD_PATH} ({os.path.getsize(SHARD_PATH)} bytes)")


if __name__ == "__main__":
    main()
