"""Removes running-header/page-number fragments that leaked into the body
text mid-sentence during PDF extraction, e.g. "...있다. 1. 교직원복무 규정
- 215 - ② 업무상..." -> "...있다. ② 업무상...". Each document's own title
(with internal whitespace treated as flexible, since the header repeats it
with inconsistent spacing) anchors the match, so only that document's own
repeated header/page-number noise is removed, not arbitrary text.
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.join(BASE_DIR, "..", "content", "regulations")


def title_pattern(title):
    # allow flexible/variant internal whitespace, matching how the running
    # header for this document appeared with slightly different spacing
    # from page to page
    escaped = re.escape(title.strip())
    flexible = re.sub(r"\\ ", r"\\s*", escaped)
    return re.compile(flexible + r"\s*-\s*\d{1,4}\s*-\s*")


def main():
    changed_files = []
    total_removed = 0
    for fname in sorted(os.listdir(CONTENT_DIR)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(CONTENT_DIR, fname)
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)

        pat = title_pattern(doc["title"])
        file_removed = 0
        for s in doc.get("sections", []):
            text = s.get("text") or ""
            new_text, n = pat.subn(" ", text)
            if n:
                new_text = re.sub(r"\s{2,}", " ", new_text).strip()
                s["text"] = new_text
                file_removed += n

        if file_removed:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=2)
            changed_files.append((fname, file_removed))
            total_removed += file_removed

    print(f"Removed {total_removed} page-break fragments across {len(changed_files)} files")
    for fn, n in changed_files:
        print(f"  {n:3d}  {fn}")


if __name__ == "__main__":
    main()
