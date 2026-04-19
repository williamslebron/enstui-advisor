"""
Enstui Ou - YouTube Channel Scraper
Step 1: Fetch videos + transcripts from @EnstuiOu and save locally.

Requirements:
    pip install google-api-python-client youtube-transcript-api python-dotenv openai-whisper
"""

import os
import json
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

# ── Config ────────────────────────────────────────────────────────────────────

load_dotenv()

YOUTUBE_API_KEY  = os.getenv("YOUTUBE_API_KEY")   # Your Google API key
CHANNEL_HANDLE   = "@EnstuiOu"                     # Target channel
OUTPUT_DIR       = Path("transcripts")             # Where files are saved
STATE_FILE       = Path("last_run_state.json")     # Tracks already-scraped videos
PREFERRED_LANGS  = ["ht", "fr", "en"]              # Haitian Creole → French → English
MAX_RESULTS      = 50                              # Videos per API call (max 50)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("scraper.log")]
)
log = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_state() -> dict:
    """Load the list of already-scraped video IDs from disk."""
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"scraped_ids": [], "last_run": None}


def save_state(state: dict):
    """Persist state to disk so we never re-scrape the same video."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def get_channel_id(youtube, handle: str) -> str:
    """Resolve a @handle to a numeric channel ID."""
    log.info(f"Resolving channel ID for {handle} ...")
    resp = youtube.search().list(
        q=handle,
        type="channel",
        part="id,snippet",
        maxResults=1
    ).execute()

    items = resp.get("items", [])
    if not items:
        raise ValueError(f"Channel not found: {handle}")

    channel_id = items[0]["id"]["channelId"]
    title      = items[0]["snippet"]["title"]
    log.info(f"  Found: {title}  (ID: {channel_id})")
    return channel_id


def fetch_video_list(youtube, channel_id: str, already_scraped: list) -> list:
    """
    Pull all video IDs + metadata for the channel.
    Skips any video already present in already_scraped.
    """
    videos   = []
    next_page = None

    log.info("Fetching video list from channel ...")

    while True:
        kwargs = dict(
            channelId=channel_id,
            type="video",
            part="id,snippet",
            maxResults=MAX_RESULTS,
            order="date"           # newest first → stops early once we hit known videos
        )
        if next_page:
            kwargs["pageToken"] = next_page

        resp      = youtube.search().list(**kwargs).execute()
        items     = resp.get("items", [])
        next_page = resp.get("nextPageToken")

        new_count = 0
        for item in items:
            vid_id = item["id"]["videoId"]
            if vid_id in already_scraped:
                continue                         # Already have this one — skip

            snippet = item["snippet"]
            videos.append({
                "id":           vid_id,
                "title":        snippet["title"],
                "description":  snippet["description"],
                "published_at": snippet["publishedAt"],
                "thumbnail":    snippet["thumbnails"].get("high", {}).get("url", ""),
                "url":          f"https://www.youtube.com/watch?v={vid_id}"
            })
            new_count += 1

        log.info(f"  Page fetched — {new_count} new videos found.")

        # If every video on this page was already scraped, no need to go further back
        if new_count == 0 or not next_page:
            break

        time.sleep(0.3)   # Be polite to the API

    log.info(f"Total new videos to process: {len(videos)}")
    return videos


def fetch_transcript(video_id: str) -> tuple[str, str]:
    """
    Try to get a transcript in order of preferred languages.
    Returns (transcript_text, source) where source is 'auto' or 'manual'.
    Raises if nothing is available.
    """
    try:
        # Try preferred languages first
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        # 1. Manual captions in preferred langs
        for lang in PREFERRED_LANGS:
            try:
                t = transcript_list.find_manually_created_transcript([lang])
                chunks = t.fetch()
                text   = " ".join(c["text"] for c in chunks)
                return text, f"manual_{lang}"
            except Exception:
                pass

        # 2. Auto-generated captions in preferred langs
        for lang in PREFERRED_LANGS:
            try:
                t = transcript_list.find_generated_transcript([lang])
                chunks = t.fetch()
                text   = " ".join(c["text"] for c in chunks)
                return text, f"auto_{lang}"
            except Exception:
                pass

        # 3. Whatever language is available (translate to English as fallback)
        try:
            t      = transcript_list.find_generated_transcript(["ht", "fr", "en", "es", "pt"])
            chunks = t.fetch()
            text   = " ".join(c["text"] for c in chunks)
            return text, f"auto_{t.language_code}"
        except Exception:
            pass

    except (TranscriptsDisabled, NoTranscriptFound):
        pass

    raise RuntimeError("No transcript available for this video.")


def save_video(video: dict, transcript: str, source: str):
    """
    Save a video's metadata + transcript as a single JSON file.
    Filename: YYYY-MM-DD_<video_id>.json
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    date_prefix = video["published_at"][:10]   # e.g. "2026-04-15"
    filename    = OUTPUT_DIR / f"{date_prefix}_{video['id']}.json"

    payload = {
        **video,
        "transcript":        transcript,
        "transcript_source": source,
        "scraped_at":        datetime.now(timezone.utc).isoformat()
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    log.info(f"  ✔  Saved: {filename.name}  [{source}]")


def save_no_transcript(video: dict, reason: str):
    """Save metadata-only file when no transcript is available."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    date_prefix = video["published_at"][:10]
    filename    = OUTPUT_DIR / f"{date_prefix}_{video['id']}_NO_TRANSCRIPT.json"

    payload = {
        **video,
        "transcript":        None,
        "transcript_source": "none",
        "skip_reason":       reason,
        "scraped_at":        datetime.now(timezone.utc).isoformat()
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    log.warning(f"  ⚠  No transcript — saved metadata only: {filename.name}")


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    if not YOUTUBE_API_KEY:
        raise EnvironmentError(
            "YOUTUBE_API_KEY is not set. "
            "Create a .env file with: YOUTUBE_API_KEY=your_key_here"
        )

    log.info("=" * 60)
    log.info("Enstui Ou Scraper — Starting")
    log.info(f"Run time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)

    state    = load_state()
    scraped  = set(state.get("scraped_ids", []))

    youtube  = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

    # Step 1 — Resolve channel
    channel_id = get_channel_id(youtube, CHANNEL_HANDLE)

    # Step 2 — Get new video list
    videos = fetch_video_list(youtube, channel_id, scraped)

    if not videos:
        log.info("Nothing new to scrape. All videos are up to date.")
        state["last_run"] = datetime.now(timezone.utc).isoformat()
        save_state(state)
        return

    # Step 3 — Fetch transcripts and save
    success = 0
    skipped = 0

    for i, video in enumerate(videos, 1):
        log.info(f"[{i}/{len(videos)}] {video['title']}")

        try:
            transcript, source = fetch_transcript(video["id"])
            save_video(video, transcript, source)
            scraped.add(video["id"])
            success += 1

        except RuntimeError as e:
            save_no_transcript(video, str(e))
            scraped.add(video["id"])   # Mark as seen so we don't retry endlessly
            skipped += 1

        time.sleep(0.5)   # Avoid rate limiting

    # Step 4 — Update state
    state["scraped_ids"] = list(scraped)
    state["last_run"]    = datetime.now(timezone.utc).isoformat()
    save_state(state)

    log.info("=" * 60)
    log.info(f"Done. ✔ {success} transcripts saved  ⚠ {skipped} skipped (no captions)")
    log.info("=" * 60)


if __name__ == "__main__":
    run()
