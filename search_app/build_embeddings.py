"""Encodes chunks.jsonl with BGE-M3, reusing embeddings for any chunk whose
(regulation, source_file, article_no, text) already exists in the current
shard so a small admin edit doesn't cost a full ~10 minute re-embed."""
import json
import os
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHUNKS_PATH = os.path.join(BASE_DIR, "chunks.jsonl")
DOCS_DATA_DIR = os.path.join(BASE_DIR, "..", "docs", "data", "embeddings")
SHARD_PATH = os.path.join(DOCS_DATA_DIR, "규정집.json")
MANIFEST_PATH = os.path.join(DOCS_DATA_DIR, "manifest.json")

EMBEDDING_MODEL = "BAAI/bge-m3"
BATCH_SIZE = 12
MAX_LENGTH = 1024
DENSE_ROUND = 6
SPARSE_ROUND = 4


def key_of(c):
    return (c["regulation"], c["source_file"], c["article_no"], c["text"])


def load_existing_shard():
    if not os.path.exists(SHARD_PATH):
        return {}
    with open(SHARD_PATH, encoding="utf-8") as f:
        existing = json.load(f)
    return {key_of(c): c for c in existing}


def main():
    os.makedirs(DOCS_DATA_DIR, exist_ok=True)

    with open(CHUNKS_PATH, encoding="utf-8") as f:
        chunks = [json.loads(line) for line in f]
    print(f"Loaded {len(chunks)} chunks")

    existing_by_key = load_existing_shard()
    print(f"Found {len(existing_by_key)} previously embedded chunks")

    to_encode = []
    for c in chunks:
        cached = existing_by_key.get(key_of(c))
        if cached is not None:
            c["dense"] = cached["dense"]
            c["sparse"] = cached["sparse"]
        else:
            to_encode.append(c)

    print(f"{len(chunks) - len(to_encode)} reused, {len(to_encode)} need (re)encoding")

    if to_encode:
        from FlagEmbedding import BGEM3FlagModel

        model = BGEM3FlagModel(EMBEDDING_MODEL, use_fp16=False)
        t0 = time.time()
        out = model.encode(
            [c["text"] for c in to_encode],
            batch_size=BATCH_SIZE,
            max_length=MAX_LENGTH,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )
        print(f"Encoded {len(to_encode)} chunks in {time.time() - t0:.1f}s")

        for c, d_vec, s_vec in zip(to_encode, out["dense_vecs"], out["lexical_weights"]):
            c["dense"] = [round(float(x), DENSE_ROUND) for x in d_vec]
            c["sparse"] = {
                str(tok): round(float(w), SPARSE_ROUND)
                for tok, w in s_vec.items()
                if float(w) != 0.0
            }

    with open(SHARD_PATH, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False)
    print(f"Wrote shard: {SHARD_PATH} ({os.path.getsize(SHARD_PATH)} bytes)")

    manifest = {
        "embeddingModel": EMBEDDING_MODEL,
        "denseDim": len(chunks[0]["dense"]) if chunks else 0,
        "sparseFormat": "token_id -> weight, zero values excluded",
        "colbert": False,
        "buildId": str(int(time.time())),
        "shards": ["규정집.json"],
    }
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"Wrote manifest: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
