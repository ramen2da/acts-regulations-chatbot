import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHUNKS_PATH = os.path.join(BASE_DIR, "chunks.jsonl")
SHARD_PATH = os.path.join(BASE_DIR, "..", "docs", "data", "embeddings", "규정집.json")

TARGET_ID = 1313

OLD = (
    "(시행일) 이 규정의 제34조의2, 제34조의3 및 제37조제4항의 개정규정은 2021년 3월 1일부터 시행한다. "
    "(개정 2020.10.16.) (시행일) 이 규정은 2020년 12월 1일부터 시행한다."
)
NEW = (
    "(시행일) 이 규정은 2020년 12월 1일부터 시행한다. "
    "(시행일) 이 규정의 제34조의2, 제34조의3 및 제37조제4항의 개정규정은 2021년 3월 1일부터 시행한다. "
    "(개정 2020.10.16.)"
)


def fix_chunks_jsonl():
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        lines = f.readlines()

    fixed = False
    for i, line in enumerate(lines):
        d = json.loads(line)
        if d["id"] == TARGET_ID:
            assert OLD in d["text"], "OLD substring not found in chunks.jsonl target chunk"
            d["text"] = d["text"].replace(OLD, NEW)
            lines[i] = json.dumps(d, ensure_ascii=False) + "\n"
            fixed = True
            break
    assert fixed, "target chunk id not found in chunks.jsonl"

    with open(CHUNKS_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print("chunks.jsonl updated")


def fix_shard_text_only():
    with open(SHARD_PATH, encoding="utf-8") as f:
        shard = json.load(f)

    target = shard[TARGET_ID]
    assert target["id"] == TARGET_ID
    assert OLD in target["text"], "OLD substring not found in shard target chunk"
    target["text"] = target["text"].replace(OLD, NEW)

    with open(SHARD_PATH, "w", encoding="utf-8") as f:
        json.dump(shard, f, ensure_ascii=False)
    print("shard text updated (embeddings re-encoded separately)")


if __name__ == "__main__":
    fix_chunks_jsonl()
    fix_shard_text_only()
