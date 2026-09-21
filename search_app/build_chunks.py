"""Canonical build step (used locally and by CI): content/regulations/*.json
-> chunks.jsonl, ready for build_embeddings.py to encode.

Unlike the old PDF-based ingest.py (kept only as the historical one-time
bootstrap), this reads the hand-editable per-regulation JSON files that the
admin page writes to, so admin edits flow straight into the search index
without ever touching a PDF again.
"""
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.join(BASE_DIR, "..", "content", "regulations")
OUT_PATH = os.path.join(BASE_DIR, "chunks.jsonl")
INDEX_PATH = os.path.join(BASE_DIR, "..", "content", "index.json")

CATEGORY_ORDER = ["정관", "대학", "대학원", "일반행정", "부속기관 및 부설기관", "산학협력단"]


def main():
    docs = []
    for fname in os.listdir(CONTENT_DIR):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(CONTENT_DIR, fname), encoding="utf-8") as f:
            docs.append(json.load(f))

    def sort_key(d):
        cat = d.get("category", "")
        cat_rank = CATEGORY_ORDER.index(cat) if cat in CATEGORY_ORDER else len(CATEGORY_ORDER)
        return (cat_rank, d.get("order", 0), d.get("title", ""))

    docs.sort(key=sort_key)

    all_chunks = []
    for d in docs:
        for s in d.get("sections", []):
            text = (s.get("text") or "").strip()
            if not text:
                continue
            article_no = s.get("no")
            article_title = s.get("title")
            all_chunks.append({
                "regulation": d["title"],
                "source_file": d.get("sourceFile", d["id"] + ".json"),
                "article_no": article_no,
                "article_title": article_title,
                "section_path": f"{d['title']} > {article_no}({article_title})"
                if article_no else d["title"],
                "pdf_page_start": s.get("pdfPageStart", 1),
                "text": text,
            })

    with open(OUT_PATH, "w", encoding="utf-8") as out:
        for idx, c in enumerate(all_chunks):
            c["id"] = idx
            out.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"Built {len(all_chunks)} chunks from {len(docs)} regulation files -> {OUT_PATH}")

    # Lightweight index for the admin page: lets it list/group all
    # regulations from one file instead of fetching all 130+ individually.
    index = [
        {"id": d["id"], "title": d["title"], "category": d.get("category", ""), "order": d.get("order", 0)}
        for d in docs
    ]
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"Wrote index: {INDEX_PATH}")


if __name__ == "__main__":
    main()
