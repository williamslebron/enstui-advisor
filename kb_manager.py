"""
kb_manager.py

Backend logic for the Knowledge Base Manager (Step 4).
Handles listing sources, deleting them, and re-indexing on demand.

Used by pages/1_📚_Upload_Books.py and pages/2_🗄️_Knowledge_Base.py
"""

import os
import logging
import hashlib
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv
from supabase import create_client, Client

from gemini_client import get_gemini_client, embed_texts

load_dotenv()

log = logging.getLogger(__name__)


# ── Client Factory ────────────────────────────────────────────────────────────

def get_supabase() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise EnvironmentError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
    return create_client(url, key)


def get_ai_client():
    """Return a configured Gemini client for embeddings."""
    return get_gemini_client()


# Backwards-compatible alias — old imports may still reference get_openai
def get_openai():
    return get_ai_client()


# ── Source Listing ────────────────────────────────────────────────────────────

def list_all_sources(supabase: Client) -> list[dict]:
    resp = supabase.table("enstui_embedded_sources") \
        .select("*") \
        .order("embedded_at", desc=True) \
        .execute()
    return resp.data or []


def get_kb_summary(supabase: Client) -> dict:
    sources      = list_all_sources(supabase)
    videos       = [s for s in sources if s["source_type"] == "video"]
    books        = [s for s in sources if s["source_type"] == "book"]
    total_chunks = sum(s.get("chunk_count", 0) for s in sources)

    return {
        "total_sources": len(sources),
        "video_count":   len(videos),
        "book_count":    len(books),
        "total_chunks":  total_chunks,
        "sources":       sources,
    }


# ── Delete Operations ─────────────────────────────────────────────────────────

def delete_source(supabase: Client, source_id: str, title: str) -> dict:
    try:
        supabase.table("enstui_chunks") \
            .delete() \
            .eq("video_id", source_id) \
            .execute()

        supabase.table("enstui_embedded_sources") \
            .delete() \
            .eq("source_id", source_id) \
            .execute()

        log.info(f"Deleted source: {title} ({source_id})")
        return {"success": True, "title": title}

    except Exception as e:
        log.error(f"Failed to delete {source_id}: {e}")
        return {"success": False, "error": str(e)}


def delete_all_books(supabase: Client) -> dict:
    books = [s for s in list_all_sources(supabase) if s["source_type"] == "book"]

    if not books:
        return {"success": True, "deleted": 0}

    errors  = []
    deleted = 0
    for book in books:
        result = delete_source(supabase, book["source_id"], book["title"])
        if result["success"]:
            deleted += 1
        else:
            errors.append(result.get("error", "unknown"))

    return {"success": len(errors) == 0, "deleted": deleted, "errors": errors}


# ── Book Upload + Embedding ───────────────────────────────────────────────────

def get_book_id(filename: str) -> str:
    return hashlib.md5(filename.encode()).hexdigest()[:12]


def source_already_exists(supabase: Client, source_id: str) -> bool:
    resp = supabase.table("enstui_embedded_sources") \
        .select("source_id") \
        .eq("source_id", source_id) \
        .execute()
    return bool(resp.data)


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    import io
    try:
        from pypdf import PdfReader
    except ImportError:
        from PyPDF2 import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages  = []

    for page_num, page in enumerate(reader.pages, 1):
        text = page.extract_text()
        if text and text.strip():
            pages.append(f"[Page {page_num}]\n{text.strip()}")

    return "\n\n".join(pages)


def chunk_text(text: str, max_tokens: int = 400, overlap: int = 50) -> list[str]:
    import tiktoken
    enc    = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text)
    chunks = []
    start  = 0
    while start < len(tokens):
        end   = min(start + max_tokens, len(tokens))
        chunk = enc.decode(tokens[start:end]).strip()
        if len(chunk) > 30:
            chunks.append(chunk)
        start += max_tokens - overlap
    return chunks


def embed_and_store_book(
    supabase:      Client,
    pdf_bytes:     bytes,
    filename:      str,
    custom_title:  str = None,
    ai_client                = None,   # preferred kwarg name
    **kwargs,                           # legacy openai_client= supported
) -> dict:
    """
    Full pipeline: PDF bytes → extract → chunk → embed (Gemini) → store in Supabase.
    """
    if ai_client is None:
        ai_client = kwargs.pop("openai_client", None)
    if ai_client is None:
        ai_client = get_ai_client()

    book_id    = get_book_id(filename)
    book_title = custom_title or Path(filename).stem.replace("_", " ").replace("-", " ").title()

    if source_already_exists(supabase, book_id):
        return {
            "success":        False,
            "already_exists": True,
            "title":          book_title,
            "message":        f'"{book_title}" is already in the knowledge base.'
        }

    try:
        raw_text = extract_text_from_pdf_bytes(pdf_bytes)
    except Exception as e:
        return {"success": False, "error": f"Could not read PDF: {e}"}

    if not raw_text.strip():
        return {
            "success": False,
            "error":   "No text found in PDF. It may be a scanned image — "
                       "use Adobe Acrobat to OCR it first."
        }

    full_text = f"BOOK: {book_title}\nSOURCE: Enstui Ou Author\n\nCONTENT:\n{raw_text}"
    chunks    = chunk_text(full_text)

    if not chunks:
        return {"success": False, "error": "Text extracted but no valid chunks produced."}

    BATCH    = 50
    all_rows = []

    try:
        for batch_start in range(0, len(chunks), BATCH):
            batch   = chunks[batch_start : batch_start + BATCH]
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

        supabase.table("enstui_chunks").insert(all_rows).execute()

        supabase.table("enstui_embedded_sources").upsert({
            "source_id":   book_id,
            "source_type": "book",
            "title":       book_title,
            "chunk_count": len(chunks),
            "embedded_at": datetime.now(timezone.utc).isoformat()
        }).execute()

        log.info(f"Book embedded: {book_title} — {len(chunks)} chunks")
        return {"success": True, "title": book_title, "chunks": len(chunks)}

    except Exception as e:
        log.error(f"Embedding failed for {book_title}: {e}")
        return {"success": False, "error": str(e)}
