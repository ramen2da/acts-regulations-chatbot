from pypdf import PdfReader
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE_DIR, "pdfs", "규정집(2026.07.11).pdf")
DEST_TXT = os.path.join(BASE_DIR, "규정집_전체텍스트.txt")

reader = PdfReader(SRC)
print("pages:", len(reader.pages))

with open(DEST_TXT, "w", encoding="utf-8") as out:
    for i, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        out.write(f"\n\n===== PAGE {i} =====\n\n")
        out.write(text)
        if i % 50 == 0:
            print(f"extracted {i}/{len(reader.pages)} pages")

print("done ->", DEST_TXT)
print("size:", os.path.getsize(DEST_TXT))
