"""
retriever.py

The search layer — used by the AI advisor in Step 3.
Embeds a query via Gemini and retrieves the most relevant chunks from Supabase.

Can also be tested standalone:
    python retriever.py "kijan pouw jere yon fi ki fret"
"""

import os
import sys
import logging
from dotenv import load_dotenv
from supabase import create_client, Client

from gemini_client import get_gemini_client, embed_one

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

log = logging.getLogger(__name__)


def get_clients():
    """
    Returns (gemini_client, supabase_client).
    Kept as a 2-tuple so callers that did `openai_client, supabase = get_clients()`
    still work; the first element is now the Gemini client.
    """
    gemini_client = get_gemini_client()
    supabase      = create_client(SUPABASE_URL, SUPABASE_KEY)
    return gemini_client, supabase


def embed_query(ai_client, query: str) -> list[float]:
    """Turn a user question into a Gemini embedding vector."""
    return embed_one(ai_client, query)


def search(
    query: str,
    match_count:     int   = 8,
    match_threshold: float = 0.45,
    source_filter:   str   = None,   # "video", "book", or None for both
    ai_client               = None,  # preferred arg name (Gemini client)
    supabase:        Client = None,
    **kwargs,                        # accepts legacy `openai_client=...` too
) -> list[dict]:
    """
    Main search function.
    Returns up to match_count chunks most relevant to the query.
    """
    # Accept legacy kwarg name from older callers / pages
    if ai_client is None:
        ai_client = kwargs.pop("openai_client", None)

    if ai_client is None or supabase is None:
        ai_client, supabase = get_clients()

    query_vector = embed_query(ai_client, query)

    response = supabase.rpc("search_enstui", {
        "query_embedding": query_vector,
        "match_threshold": match_threshold,
        "match_count":     match_count,
        "source_filter":   source_filter
    }).execute()

    return response.data or []


def format_context_for_llm(results: list[dict]) -> str:
    """
    Format retrieved chunks into a clean context block
    ready to be injected into the AI advisor's prompt.
    """
    if not results:
        return "No relevant content found in the knowledge base."

    lines = []
    for i, r in enumerate(results, 1):
        source_label = (
            f"📗 Book: {r['source_name']}" if r["source_type"] == "book"
            else f"📺 Video: {r['title']}"
        )
        url_line = f"   URL: {r['url']}" if r.get("url") else ""
        sim      = r.get("similarity", 0)

        lines.append(
            f"[Context {i}] {source_label} (relevance: {sim:.2f})\n"
            f"{url_line}\n"
            f"{r['chunk_text']}\n"
        )

    return "\n---\n".join(lines)


def get_source_stats(supabase: Client = None) -> dict:
    """Quick summary of what's in the database."""
    if supabase is None:
        _, supabase = get_clients()

    sources = supabase.table("enstui_embedded_sources") \
        .select("source_type, title, chunk_count, embedded_at") \
        .order("embedded_at", desc=True) \
        .execute()

    stats = {"videos": [], "books": [], "total_chunks": 0}

    for row in (sources.data or []):
        stats["total_chunks"] += row.get("chunk_count", 0)
        if row["source_type"] == "book":
            stats["books"].append(row["title"])
        else:
            stats["videos"].append(row["title"])

    return stats


# ── Standalone test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Teknik Zonbifye"

    print(f"\n🔍 Query: {query}\n")

    ai_client, supabase = get_clients()
    results = search(query, match_count=5, ai_client=ai_client, supabase=supabase)

    if not results:
        print("No results found. Make sure you've run embed_transcripts.py first.")
    else:
        print(f"Found {len(results)} relevant chunks:\n")
        for r in results:
            print(f"  [{r['similarity']:.3f}] {r['title']}")
            print(f"           {r['chunk_text'][:120]}...")
            print()

    stats = get_source_stats(supabase)
    print(f"\n📊 Database: {len(stats['videos'])} videos, "
          f"{len(stats['books'])} books, {stats['total_chunks']} total chunks")
