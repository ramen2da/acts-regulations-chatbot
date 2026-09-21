"""Collapses double spaces and removes stray spaces before closing
punctuation (". ," ")") across all regulation content."""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.join(BASE_DIR, "..", "content", "regulations")


def clean(text):
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r" ([.,)])", r"\1", text)
    return text.strip()


def main():
    changed = 0
    for fname in sorted(os.listdir(CONTENT_DIR)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(CONTENT_DIR, fname)
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)

        file_changed = False
        for s in doc.get("sections", []):
            text = s.get("text") or ""
            new_text = clean(text)
            if new_text != text:
                s["text"] = new_text
                file_changed = True

        if file_changed:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=2)
            changed += 1

    print(f"Cleaned whitespace/punctuation in {changed} files")


if __name__ == "__main__":
    main()
