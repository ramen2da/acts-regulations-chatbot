import os
import json
import time
from FlagEmbedding import BGEM3FlagModel

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHUNKS_PATH = os.path.join(BASE_DIR, "chunks.jsonl")
DOCS_DATA_DIR = os.path.join(BASE_DIR, "..", "docs", "data", "embeddings")

EMBEDDING_MODEL = "BAAI/bge-m3"
BATCH_SIZE = 12
MAX_LENGTH = 1024
DENSE_ROUND = 6
SPARSE_ROUND = 4


def load_chunks():
    chunks = []
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        for line in f:
            chunks.append(json.loads(line))
    return chunks


def encode_batches(model, chunks):
    texts = [c["text"] for c in chunks]
    out = model.encode(
        texts,
        batch_size=BATCH_SIZE,
        max_length=MAX_LENGTH,
        return_dense=True,
        return_sparse=True,
        return_colbert_vecs=False,
    )
    dense = out["dense_vecs"]
    sparse = out["lexical_weights"]

    for c, d_vec, s_vec in zip(chunks, dense, sparse):
        c["dense"] = [round(float(x), DENSE_ROUND) for x in d_vec]
        c["sparse"] = {
            str(tok): round(float(w), SPARSE_ROUND)
            for tok, w in s_vec.items()
            if float(w) != 0.0
        }
    return chunks


def main():
    os.makedirs(DOCS_DATA_DIR, exist_ok=True)

    chunks = load_chunks()
    print(f"Loaded {len(chunks)} chunks")

    model = BGEM3FlagModel(EMBEDDING_MODEL, use_fp16=False)
    print("Model loaded")

    t0 = time.time()
    chunks = encode_batches(model, chunks)
    print(f"Encoded {len(chunks)} chunks in {time.time() - t0:.1f}s")

    shard_path = os.path.join(DOCS_DATA_DIR, "규정집.json")
    with open(shard_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False)
    print(f"Wrote shard: {shard_path} ({os.path.getsize(shard_path)} bytes)")

    manifest = {
        "embeddingModel": EMBEDDING_MODEL,
        "denseDim": len(chunks[0]["dense"]) if chunks else 0,
        "sparseFormat": "token_id -> weight, zero values excluded",
        "colbert": False,
        "buildId": str(int(time.time())),
        "shards": ["규정집.json"],
    }
    manifest_path = os.path.join(DOCS_DATA_DIR, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"Wrote manifest: {manifest_path}")


if __name__ == "__main__":
    main()
