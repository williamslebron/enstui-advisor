"""
embed_books.py

Step 2B: Ingest PDF books from the /books folder,
         embed their content via Gemini, and store in Supabase
         alongside video data.

Usage:
    python embed_books.py

Requirements:
    pip install google-genai supabase python-dotenv tiktoken pypdf
"""

import os
import hashlib
import logging
import time
from pathlib import Path
from datetime import datetime, timezone

import tiktoken
from dotenv import load_dotenv
from supabase import create_client, Client

from gemini_client import get_gemini_client, embed_texts

try:
    from pypdf import PdfReader
except ImportError:
    from PyPDF2 import PdfReader

# ── Config ────────────────────────────────────────────────────────────────────

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

BOOKS_DIR     = Path("books")
CHUNK_TOKENS  = 400
CHUNK_OVERLAP = 50
BATCH_SIZE    = 50

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("embedder.log")]
)
log = logging.getLogger(__name__)


# ── PDF Extraction ────────────────────────────────────────────────────────────

def extract_pdf_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    pages  = []

    for page_num, page in enumerate(reader.pages, 1):
        text = page.extract_text()
        if text and text.strip():
            pages.append(f"[Page {page_num}]\n{text.strip()}")

    full_text = "\n\n".join(pages)
    log.info(f"  Extracted {len(reader.pages)} pages, {len(full_text)} chars")
    return full_text


def get_book_id(pdf_path: Path) -> str:
    return hashlib.md5(pdf_path.name.encode()).hexdigest()[:12]


# ── Chunking (same as embed_transcripts.py) ───────────────────────────────────

def chunk_text(text: str, max_tokens: int = CHUNK_TOKENS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    enc    = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text)
    chunks = []
    start  = 0

    while start < len(tokens):
        end        = min(start + max_tokens, len(tokens))
        chunk_toks = tokens[start:end]
        chunks.append(enc.decode(chunk_toks).strip())
        start += max_tokens - overlap

    return [c for c in chunks if len(c) > 30]


# ── Upload helpers ────────────────────────────────────────────────────────────

def get_embedded_ids(supabase: Client) -> set:
    resp = supabase.table("enstui_embedded_sources").select("source_id").execute()
    return {row["source_id"] for row in (resp.data or [])}


def upload_chunks(supabase: Client, rows: list[dict]):
    supabase.table("enstui_chunks").insert(rows).execute()


def mark_source_done(supabase: Client, source_id: str, title: str, chunk_count: int):
    supabase.table("enstui_embedded_sources").upsert({
        "source_id":   source_id,
        "source_type": "book",
        "title":       title,
        "chunk_count": chunk_count,
        "embedded_at": datetime.now(timezone.utc).isoformat()
    }).execute()


# ── Main ──────────────────────────────────────────────────────────────────────

def process_book(
    pdf_path: Path,
    ai_client,
    supabase: Client,
    already_embedded: set
):
    book_id    = get_book_id(pdf_path)
    book_title = pdf_path.stem.replace("_", " ").replace("-", " ").title()

    if book_id in already_embedded:
        log.info(f"  ⏭  Already embedded — skipping: {book_title}")
        return 0

    log.info(f"  📚 Processing book: {book_title}")

    try:
        raw_text = extract_pdf_text(pdf_path)
    except Exception as e:
        log.error(f"  ✗  Could not read PDF: {e}")
        return 0

    if not raw_text.strip():
        log.warning(f"  ⚠  No text extracted from {pdf_path.name} — may be a scanned image PDF.")
        log.warning("     Use OCR tools like Adobe Acrobat or pdfplumber to pre-process it first.")
        return 0

    header    = f"BOOK: {book_title}\nSOURCE: Enstui Ou Author\n\nCONTENT:\n"
    full_text = header + raw_text

    chunks = chunk_text(full_text)
    log.info(f"  Split into {len(chunks)} chunks")

    all_rows = []
    for batch_start in range(0, len(chunks), BATCH_SIZE):
        batch   = chunks[batch_start : batch_start + BATCH_SIZE]
        vectors = embed_texts(ai_client, batch)

        for i, (chunk, vector) in enumerate(zip(batch, vectors)):
            all_rows.append({
                "video_id":     book_id,
                "title":        book_title,
                "published_at": None,
                "url":          None,
                "source_type":  "book",
                "source_name":  book_title,
                "chunk_index":  batch_start + i,
                "chunk_text":   chunk,
                "embedding":    vector,
            })

        time.sleep(0.2)

    upload_chunks(supabase, all_rows)
    mark_source_done(supabase, book_id, book_title, len(chunks))
    already_embedded.add(book_id)

    log.info(f"  ✔  Done: {book_title} — {len(chunks)} chunks embedded")
    return len(chunks)


def run():
    for var in ["GEMINI_API_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_KEY"]:
        if not os.getenv(var):
            raise EnvironmentError(f"{var} is not set in .env")

    BOOKS_DIR.mkdir(exist_ok=True)

    pdf_files = list(BOOKS_DIR.glob("*.pdf"))

    if not pdf_files:
        log.warning(f"No PDF files found in /{BOOKS_DIR}. Add books there and re-run.")
        return

    log.info("=" * 60)
    log.info("Enstui Ou Book Embedder — Starting (Gemini)")
    log.info(f"Found {len(pdf_files)} PDF(s) to process")
    log.info("=" * 60)

    ai_client        = get_gemini_client()
    supabase         = create_client(SUPABASE_URL, SUPABASE_KEY)
    already_embedded = get_embedded_ids(supabase)

    total_chunks = 0
    for i, pdf_path in enumerate(pdf_files, 1):
        log.info(f"[{i}/{len(pdf_files)}] {pdf_path.name}")
        try:
            total_chunks += process_book(pdf_path, ai_client, supabase, already_embedded)
        except Exception as e:
            log.error(f"  ✗  Error: {e}")

    log.info("=" * 60)
    log.info(f"Books embedded. Total new chunks stored: {total_chunks}")
    log.info("=" * 60)


if __name__ == "__main__":
    run()
