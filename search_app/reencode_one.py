import json
import os
from FlagEmbedding import BGEM3FlagModel

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SHARD_PATH = os.path.join(BASE_DIR, "..", "docs", "data", "embeddings", "규정집.json")

TARGET_ID = 1313
EMBEDDING_MODEL = "BAAI/bge-m3"
MAX_LENGTH = 1024
DENSE_ROUND = 6
SPARSE_ROUND = 4


def main():
    with open(SHARD_PATH, encoding="utf-8") as f:
        shard = json.load(f)

    target = shard[TARGET_ID]
    assert target["id"] == TARGET_ID

    model = BGEM3FlagModel(EMBEDDING_MODEL, use_fp16=False)
    out = model.encode(
        [target["text"]],
        max_length=MAX_LENGTH,
        return_dense=True,
        return_sparse=True,
        return_colbert_vecs=False,
    )
    dense = out["dense_vecs"][0]
    sparse = out["lexical_weights"][0]

    target["dense"] = [round(float(x), DENSE_ROUND) for x in dense]
    target["sparse"] = {
        str(tok): round(float(w), SPARSE_ROUND)
        for tok, w in sparse.items()
        if float(w) != 0.0
    }

    with open(SHARD_PATH, "w", encoding="utf-8") as f:
        json.dump(shard, f, ensure_ascii=False)
    print("Re-encoded chunk", TARGET_ID)


if __name__ == "__main__":
    main()
