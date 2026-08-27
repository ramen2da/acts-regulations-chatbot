import os
import re
import json
from pypdf import PdfReader

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_DIR = os.path.join(BASE_DIR, "..", "pdfs")
MASTER_TEXT_PATH = os.path.join(BASE_DIR, "..", "규정집_전체텍스트.txt")
OUT_PATH = os.path.join(BASE_DIR, "chunks.jsonl")
MASTER_FILE = "규정집(2026.07.11).pdf"

PAGE_MARKER_RE = re.compile(r"===== PAGE (\d+) =====\n")
# each regulation's page repeats a running header "N. 제목" followed by
# a printed page number line "- 123 -"; the header text (before any "-"
# suffix such as a department name) stays constant while a regulation
# spans multiple pages, and changes exactly when a new regulation starts.
HEADER_RE = re.compile(r"^(\d+\.\s*[^\n]{1,60}?)\n-\s*\d+\s*-", re.MULTILINE)
ARTICLE_RE = re.compile(r"(제\s*\d+\s*조(?:의\s*\d+)?\s*\([^)]{0,60}\))")
WHITESPACE_RE = re.compile(r"[ \t\r\n]+")


def normalize_whitespace(text):
    return WHITESPACE_RE.sub(" ", text).strip()


def load_pages(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    parts = PAGE_MARKER_RE.split(text)
    # parts[0] is content before the first marker (should be empty/whitespace)
    pages = {}
    for i in range(1, len(parts), 2):
        page_no = int(parts[i])
        pages[page_no] = parts[i + 1]
    return pages


def page_header_title(page_text):
    """Returns the running-header title as displayed (whitespace collapsed),
    or None if this page doesn't carry the 'N. 제목 / - page -' header pattern."""
    m = HEADER_RE.match(page_text.strip())
    if not m:
        return None
    return normalize_whitespace(m.group(1).split("-")[0])


GLYPH_FIXES = {
    "힉위": "학위",  # font substitution glitch on a handful of pages
    "․": "·",  # ONE DOT LEADER vs MIDDLE DOT, used inconsistently for "·"
}


def header_group_key(title):
    """Whitespace and leading item numbers vary page-to-page for the same
    regulation's running header (e.g. '조교인사규정' vs '조교인사 규정', or
    a stray renumbering like '24.' vs '26.' for the same regulation), so
    grouping compares the title text only, whitespace stripped."""
    text = re.sub(r"^\d+\.\s*", "", title)
    for bad, good in GLYPH_FIXES.items():
        text = text.replace(bad, good)
    return re.sub(r"\s+", "", text)


def group_into_regulations(pages):
    """Walk pages in order, grouping consecutive pages that share the same
    running-header key into one regulation. Pages without a recognizable
    header (cover pages, section dividers) attach to whichever segment is
    currently open."""
    segments = []  # list of {"title": str, "key": str, "pages": [(page_no, text), ...]}
    current = None

    for page_no in sorted(pages):
        text = pages[page_no]
        title = page_header_title(text)
        key = header_group_key(title) if title is not None else None

        if key is not None and (current is None or key != current["key"]):
            current = {"title": title, "key": key, "pages": []}
            segments.append(current)
        elif current is None:
            current = {"title": "(표지/목차)", "key": None, "pages": []}
            segments.append(current)

        current["pages"].append((page_no, text))

    # A regulation can resurface in a later, non-adjacent segment (e.g. an
    # appendix/서식 block placed after an intervening regulation). Merge
    # every segment sharing a key back into its first occurrence, keeping
    # documents in first-seen order.
    merged = {}
    ordered = []
    for seg in segments:
        if seg["key"] is None:
            ordered.append(seg)
            continue
        if seg["key"] in merged:
            merged[seg["key"]]["pages"].extend(seg["pages"])
        else:
            merged[seg["key"]] = seg
            ordered.append(seg)

    return ordered


def split_articles(regulation_name, pages, source_file):
    """Split one regulation's pages into article-level chunks."""
    full_text = "\n".join(text for _, text in pages)

    page_bounds = []
    offset = 0
    for page_no, text in pages:
        page_bounds.append((page_no, offset))
        offset += len(text) + 1

    def page_at(off):
        pno = pages[0][0] if pages else 1
        for p, start in page_bounds:
            if off >= start:
                pno = p
            else:
                break
        return pno

    matches = list(ARTICLE_RE.finditer(full_text))
    chunks = []

    def make_chunk(article_no, article_title, start, end):
        body = normalize_whitespace(full_text[start:end])
        if not body:
            return None
        return {
            "regulation": regulation_name,
            "source_file": source_file,
            "article_no": article_no,
            "article_title": article_title,
            "section_path": f"{regulation_name} > {article_no}({article_title})"
            if article_no else regulation_name,
            "pdf_page_start": page_at(start),
            "text": body,
        }

    if not matches:
        chunk = make_chunk(None, None, 0, len(full_text))
        if chunk:
            chunks.append(chunk)
        return chunks

    preamble = make_chunk(None, "전문/개정이력", 0, matches[0].start())
    if preamble:
        chunks.append(preamble)

    for i, m in enumerate(matches):
        header = m.group(1)
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)

        no_title_match = re.match(r"제\s*\d+\s*조(?:의\s*\d+)?", header)
        article_no = no_title_match.group(0).replace(" ", "") if no_title_match else header
        title_match = re.search(r"\(([^)]{0,60})\)", header)
        article_title = title_match.group(1) if title_match else ""

        chunk = make_chunk(article_no, article_title, start, end)
        if chunk:
            chunks.append(chunk)

    return chunks


def extract_standalone_pdf_pages(path):
    reader = PdfReader(path)
    return [(i, page.extract_text() or "") for i, page in enumerate(reader.pages, 1)]


def main():
    pages = load_pages(MASTER_TEXT_PATH)
    print(f"Loaded {len(pages)} pages from {MASTER_TEXT_PATH}")

    segments = group_into_regulations(pages)
    print(f"Grouped into {len(segments)} regulation segments")

    all_chunks = []
    for i, seg in enumerate(segments, 1):
        chunks = split_articles(seg["title"], seg["pages"], MASTER_FILE)
        all_chunks.extend(chunks)
        print(f"[{i}/{len(segments)}] {seg['title']}: {len(seg['pages'])}p, {len(chunks)} chunks")

    # standalone PDFs: each individual file is its own regulation, no
    # running-header grouping needed since there's nothing else to merge with
    standalone_files = sorted(
        f for f in os.listdir(PDF_DIR)
        if f.lower().endswith(".pdf") and f != MASTER_FILE
    )
    print(f"\nFound {len(standalone_files)} standalone regulation PDFs")
    for i, fname in enumerate(standalone_files, 1):
        regulation_name = os.path.splitext(fname)[0]
        pdf_pages = extract_standalone_pdf_pages(os.path.join(PDF_DIR, fname))
        chunks = split_articles(regulation_name, pdf_pages, fname)
        all_chunks.extend(chunks)
        print(f"[{i}/{len(standalone_files)}] {fname}: {len(pdf_pages)}p, {len(chunks)} chunks")

    with open(OUT_PATH, "w", encoding="utf-8") as out:
        for idx, c in enumerate(all_chunks):
            c["id"] = idx
            out.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"\nTotal chunks: {len(all_chunks)}")
    print(f"Written to: {OUT_PATH}")


if __name__ == "__main__":
    main()
