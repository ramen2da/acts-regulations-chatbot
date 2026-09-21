"""Detects PDF-extraction spacing loss (long runs of Korean text with no
spaces) and uses PyKoSpacing (a pretrained model, no domain training
needed) to reinsert word spacing in the affected sections only."""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.join(BASE_DIR, "..", "content", "regulations")

RUN_RE = re.compile(r"[가-힣]{20,}")
# PyKoSpacing sometimes leaves the header run-on, e.g. "제1조(목적)본 대학교는..."
HEADER_GLUE_RE = re.compile(r"(제\s*\d+\s*조(?:의\s*\d+)?\([^)]{0,60}\))(?=[^\s])")


def has_run(text):
    return bool(RUN_RE.search(text or ""))


def load_docs():
    docs = {}
    for fname in sorted(os.listdir(CONTENT_DIR)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(CONTENT_DIR, fname)
        with open(path, encoding="utf-8") as f:
            docs[fname] = json.load(f)
    return docs


def main():
    docs = load_docs()

    affected = []
    for fname, doc in docs.items():
        for s in doc.get("sections", []):
            if has_run(s.get("text") or ""):
                affected.append((fname, doc, s))
    print(f"{len(affected)} sections across {len({a[0] for a in affected})} files need spacing")

    from pykospacing import Spacing

    spacing = Spacing()

    changed_files = set()
    for i, (fname, doc, s) in enumerate(affected, 1):
        original = s["text"]
        corrected = spacing(original)
        corrected = HEADER_GLUE_RE.sub(r"\1 ", corrected)
        if corrected != original:
            s["text"] = corrected
            changed_files.add(fname)
        if i % 20 == 0:
            print(f"  {i}/{len(affected)}")

    for fname in changed_files:
        with open(os.path.join(CONTENT_DIR, fname), "w", encoding="utf-8") as f:
            json.dump(docs[fname], f, ensure_ascii=False, indent=2)

    print(f"\nUpdated {len(changed_files)} files:")
    for fn in sorted(changed_files):
        print(" ", fn)


if __name__ == "__main__":
    main()
