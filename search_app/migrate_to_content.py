"""One-time migration: chunks.jsonl (derived from PDFs) -> content/regulations/*.json
(the new hand-editable source of truth used by the admin page and CI rebuild)."""
import json
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHUNKS_PATH = os.path.join(BASE_DIR, "chunks.jsonl")
CONTENT_DIR = os.path.join(BASE_DIR, "..", "content", "regulations")

# Same category slice sizes used by ingest.py's assembly order.
CATEGORY_COUNTS = [
    ("정관", 3),
    ("대학", 1),
    ("대학원", 13),
    ("일반행정", 95),
    ("부속기관 및 부설기관", 19),
    ("산학협력단", 2),
]


def section_type(article_no):
    if not article_no:
        return "note"
    if article_no.startswith("별표"):
        return "table"
    if article_no.startswith("별지") or "서식" in article_no:
        return "form"
    return "article"


def slugify(name):
    slug = re.sub(r"[^\w가-힣.\-]+", "_", name).strip("_")
    return slug or "unnamed"


def main():
    os.makedirs(CONTENT_DIR, exist_ok=True)

    with open(CHUNKS_PATH, encoding="utf-8") as f:
        chunks = [json.loads(line) for line in f]

    regs = []  # list of {"regulation":.., "source_file":.., "sections": [...]}
    index = {}
    for c in chunks:
        key = c["regulation"]
        if key not in index:
            index[key] = {"regulation": key, "source_file": c["source_file"], "sections": []}
            regs.append(index[key])
        index[key]["sections"].append(c)

    # drop the non-regulation cover/TOC bucket
    regs = [r for r in regs if r["regulation"] != "(표지/목차)"]

    total_expected = sum(n for _, n in CATEGORY_COUNTS)
    if len(regs) != total_expected:
        raise SystemExit(
            f"Expected {total_expected} regulations from CATEGORY_COUNTS, got {len(regs)}. "
            "Update CATEGORY_COUNTS to match the current corpus before migrating."
        )

    cursor = 0
    written = 0
    for category, count in CATEGORY_COUNTS:
        for order, reg in enumerate(regs[cursor : cursor + count], start=1):
            slug = slugify(reg["regulation"])
            doc = {
                "id": slug,
                "title": reg["regulation"],
                "category": category,
                "order": order,
                "sourceFile": reg["source_file"],
                "sections": [
                    {
                        "type": section_type(s["article_no"]),
                        "no": s["article_no"],
                        "title": s["article_title"],
                        "text": s["text"],
                    }
                    for s in reg["sections"]
                ],
            }
            path = os.path.join(CONTENT_DIR, f"{slug}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=2)
            written += 1
        cursor += count

    print(f"Wrote {written} regulation files to {CONTENT_DIR}")


if __name__ == "__main__":
    main()
