"""
embed_transcripts.py

Step 2A: Read transcript JSON files from Step 1, chunk them,
         create embeddings via Gemini, and store in Supabase.

Usage:
    python embed_transcripts.py

Requirements:
    pip install google-genai supabase python-dotenv tiktoken
"""

import os
import json
import logging
import time
from pathlib import Path
from datetime import datetime, timezone

import tiktoken
from dotenv import load_dotenv
from supabase import create_client, Client

from gemini_client import get_gemini_client, embed_texts

# ── Config ────────────────────────────────────────────────────────────────────

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

TRANSCRIPTS_DIR  = Path("transcripts")
CHUNK_TOKENS     = 400
CHUNK_OVERLAP    = 50
BATCH_SIZE       = 50       # Gemini embedding batch size

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("embedder.log")]
)
log = logging.getLogger(__name__)


# ── Text Chunking ─────────────────────────────────────────────────────────────

def chunk_text(text: str, max_tokens: int = CHUNK_TOKENS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Split text into overlapping token-based chunks.
    Overlap ensures context isn't lost at chunk boundaries.
    """
    enc    = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text)
    chunks = []
    start  = 0

    while start < len(tokens):
        end        = min(start + max_tokens, len(tokens))
        chunk_toks = tokens[start:end]
        chunk_str  = enc.decode(chunk_toks).strip()
        chunks.append(chunk_str)
        start += max_tokens - overlap

    return [c for c in chunks if len(c) > 30]


# ── Supabase Upload ───────────────────────────────────────────────────────────

def get_embedded_ids(supabase: Client) -> set:
    resp = supabase.table("enstui_embedded_sources").select("source_id").execute()
    return {row["source_id"] for row in (resp.data or [])}


def upload_chunks(supabase: Client, rows: list[dict]):
    supabase.table("enstui_chunks").insert(rows).execute()


def mark_source_done(supabase: Client, source_id: str, source_type: str, title: str, chunk_count: int):
    supabase.table("enstui_embedded_sources").upsert({
        "source_id":   source_id,
        "source_type": source_type,
        "title":       title,
        "chunk_count": chunk_count,
        "embedded_at": datetime.now(timezone.utc).isoformat()
    }).execute()


# ── Main Pipeline ─────────────────────────────────────────────────────────────

def process_video_file(
    json_path: Path,
    ai_client,
    supabase: Client,
    already_embedded: set
):
    with open(json_path, "r", encoding="utf-8") as f:
        video = json.load(f)

    video_id   = video.get("id", "")
    title      = video.get("title", "Untitled")
    transcript = video.get("transcript")

    if video_id in already_embedded:
        log.info(f"  ⏭  Already embedded — skipping: {title[:50]}")
        return 0

    if not transcript:
        log.warning(f"  ⚠  No transcript — skipping: {title[:50]}")
        return 0

    description = video.get("description", "")[:500]
    full_text   = f"VIDEO TITLE: {title}\n\nDESCRIPTION: {description}\n\nTRANSCRIPT:\n{transcript}"

    chunks = chunk_text(full_text)
    log.info(f"  📄 {title[:55]}  →  {len(chunks)} chunks")

    all_rows = []
    for batch_start in range(0, len(chunks), BATCH_SIZE):
        batch   = chunks[batch_start : batch_start + BATCH_SIZE]
        vectors = embed_texts(ai_client, batch)

        for i, (chunk, vector) in enumerate(zip(batch, vectors)):
            all_rows.append({
                "video_id":     video_id,
                "title":        title,
                "published_at": video.get("published_at"),
                "url":          video.get("url", ""),
                "source_type":  "video",
                "source_name":  None,
                "chunk_index":  batch_start + i,
                "chunk_text":   chunk,
                "embedding":    vector,
            })

        time.sleep(0.2)   # Stay well under Gemini free-tier rate limits

    upload_chunks(supabase, all_rows)
    mark_source_done(supabase, video_id, "video", title, len(chunks))
    already_embedded.add(video_id)

    return len(chunks)


def run():
    for var in ["GEMINI_API_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_KEY"]:
        if not os.getenv(var):
            raise EnvironmentError(f"{var} is not set in .env")

    log.info("=" * 60)
    log.info("Enstui Ou Embedder — Starting (Gemini)")
    log.info(f"Run time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)

    ai_client = get_gemini_client()
    supabase  = create_client(SUPABASE_URL, SUPABASE_KEY)

    already_embedded = get_embedded_ids(supabase)
    log.info(f"Already embedded: {len(already_embedded)} sources")

    json_files = sorted([
        f for f in TRANSCRIPTS_DIR.glob("*.json")
        if "_NO_TRANSCRIPT" not in f.name
    ])

    log.info(f"Transcript files found: {len(json_files)}")

    total_chunks = 0
    total_videos = 0

    for i, json_file in enumerate(json_files, 1):
        log.info(f"[{i}/{len(json_files)}] Processing: {json_file.name}")
        try:
            chunks = process_video_file(json_file, ai_client, supabase, already_embedded)
            if chunks > 0:
                total_chunks += chunks
                total_videos += 1
        except Exception as e:
            log.error(f"  ✗  Failed: {e}")

    log.info("=" * 60)
    log.info(f"Done. Embedded {total_videos} new videos → {total_chunks} total chunks stored.")
    log.info("=" * 60)


if __name__ == "__main__":
    run()
