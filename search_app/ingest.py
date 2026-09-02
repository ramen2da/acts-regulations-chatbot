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


# Display/search order: 정관 - 대학 - 대학원 - 일반행정 - 부속기관 및 부설기관 - 산학협력단.
# The compiled 규정집's own page order already runs 정관 -> 일반행정 -> 부속기관 ->
# 산학협력단 (matching its table of contents), so only 대학/대학원 need inserting
# between 정관 and 일반행정. Within the master doc, 정관 is always the first 3
# regulation segments (정관/정관시행세칙/법인사무분장규정) after the cover segment,
# 일반행정 is the next 95 (Ⅱ.A~D), 부속기관 the next 19 (Ⅲ), 산학협력단 the last 2 (Ⅳ).
CHARTER_COUNT = 3
GENERAL_ADMIN_COUNT = 95
AFFILIATED_COUNT = 19

UNIVERSITY_FILES = [
    "학칙_260623개정(재입학개정 반영).pdf",
]

GRADUATE_SCHOOL_FILES = [
    "대학원_학칙(2025-09-25).pdf",
    "대학원_학사내규(2026-01-20).pdf",
    "교육과정_및_이수학점에_관한_규정(2026-04-30).pdf",
    "재입학에_관한_규정.pdf",
    "전과_및_전공변경에_관한_규정.pdf",
    "청강에_관한_규정(2024-09-12).pdf",
    "개인지도에_관한_규정(2023-09-18).pdf",
    "학점교환제에_관한_규정.pdf",
    "학위논문에_관한_규정(2025-04-25).pdf",
    "장학금_지급에_관한_규정.pdf",
    "장학금운영_시행세칙(2026-01-20).pdf",
    "전문상담교사(1급)_양성과정_운영규정.pdf",
    "경건생활관리규정.pdf",
]


def process_master_group(segments, label):
    chunks = []
    for i, seg in enumerate(segments, 1):
        seg_chunks = split_articles(seg["title"], seg["pages"], MASTER_FILE)
        chunks.extend(seg_chunks)
        print(f"  [{label} {i}/{len(segments)}] {seg['title']}: {len(seg['pages'])}p, {len(seg_chunks)} chunks")
    return chunks


def process_standalone_group(filenames, label):
    chunks = []
    for i, fname in enumerate(filenames, 1):
        regulation_name = os.path.splitext(fname)[0]
        pdf_pages = extract_standalone_pdf_pages(os.path.join(PDF_DIR, fname))
        reg_chunks = split_articles(regulation_name, pdf_pages, fname)
        chunks.extend(reg_chunks)
        print(f"  [{label} {i}/{len(filenames)}] {fname}: {len(pdf_pages)}p, {len(reg_chunks)} chunks")
    return chunks


def main():
    pages = load_pages(MASTER_TEXT_PATH)
    print(f"Loaded {len(pages)} pages from {MASTER_TEXT_PATH}")

    segments = group_into_regulations(pages)
    print(f"Grouped into {len(segments)} regulation segments")

    cover = segments[0:1]
    charter = segments[1 : 1 + CHARTER_COUNT]
    general_admin = segments[1 + CHARTER_COUNT : 1 + CHARTER_COUNT + GENERAL_ADMIN_COUNT]
    affiliated = segments[
        1 + CHARTER_COUNT + GENERAL_ADMIN_COUNT
        : 1 + CHARTER_COUNT + GENERAL_ADMIN_COUNT + AFFILIATED_COUNT
    ]
    industry = segments[1 + CHARTER_COUNT + GENERAL_ADMIN_COUNT + AFFILIATED_COUNT :]

    all_chunks = []
    print("\n[정관]")
    all_chunks += process_master_group(charter, "정관")
    print("\n[대학]")
    all_chunks += process_standalone_group(UNIVERSITY_FILES, "대학")
    print("\n[대학원]")
    all_chunks += process_standalone_group(GRADUATE_SCHOOL_FILES, "대학원")
    print("\n[일반행정]")
    all_chunks += process_master_group(general_admin, "일반행정")
    print("\n[부속기관 및 부설기관]")
    all_chunks += process_master_group(affiliated, "부속기관")
    print("\n[산학협력단]")
    all_chunks += process_master_group(industry, "산학협력단")
    print("\n[표지/목차 (검색에는 노출되지 않음)]")
    all_chunks += process_master_group(cover, "표지")

    accounted_for = set(UNIVERSITY_FILES) | set(GRADUATE_SCHOOL_FILES) | {MASTER_FILE}
    leftover_files = sorted(
        f for f in os.listdir(PDF_DIR)
        if f.lower().endswith(".pdf") and f not in accounted_for
    )
    if leftover_files:
        print(f"\n[분류되지 않은 PDF {len(leftover_files)}개 - UNIVERSITY_FILES/GRADUATE_SCHOOL_FILES에 추가 필요]")
        all_chunks += process_standalone_group(leftover_files, "미분류")

    with open(OUT_PATH, "w", encoding="utf-8") as out:
        for idx, c in enumerate(all_chunks):
            c["id"] = idx
            out.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"\nTotal chunks: {len(all_chunks)}")
    print(f"Written to: {OUT_PATH}")


if __name__ == "__main__":
    main()
