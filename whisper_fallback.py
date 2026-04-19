"""
whisper_fallback.py

Run this AFTER scraper.py to process any videos that had no captions.
It downloads the audio and uses OpenAI Whisper to transcribe them locally.

Usage:
    python whisper_fallback.py

Requirements:
    pip install yt-dlp openai-whisper
    Also requires ffmpeg: https://ffmpeg.org/download.html
"""

import json
import logging
import subprocess
import tempfile
from pathlib import Path

import whisper

TRANSCRIPTS_DIR = Path("transcripts")
WHISPER_MODEL   = "medium"   # Options: tiny, base, small, medium, large
                              # "medium" gives best balance for Haitian Creole

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def download_audio(video_url: str, output_path: str) -> bool:
    """Download audio-only using yt-dlp."""
    try:
        subprocess.run([
            "yt-dlp",
            "-x",                          # Extract audio only
            "--audio-format", "mp3",
            "--audio-quality", "5",        # Medium quality (enough for speech)
            "-o", output_path,
            video_url
        ], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        log.error(f"yt-dlp failed: {e.stderr.decode()}")
        return False


def transcribe_with_whisper(audio_path: str, model) -> str:
    """Transcribe audio file using Whisper."""
    log.info(f"  Transcribing with Whisper ({WHISPER_MODEL}) ...")
    result = model.transcribe(audio_path, task="transcribe")
    return result["text"]


def update_json_file(json_path: Path, transcript: str):
    """Update an existing JSON file to add the Whisper transcript."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    data["transcript"]        = transcript
    data["transcript_source"] = f"whisper_{WHISPER_MODEL}"
    data["skip_reason"]       = None

    # Rename: remove _NO_TRANSCRIPT suffix
    new_path = Path(str(json_path).replace("_NO_TRANSCRIPT", ""))

    with open(new_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    json_path.unlink()   # Remove old file
    log.info(f"  ✔  Updated: {new_path.name}")


def run():
    no_transcript_files = list(TRANSCRIPTS_DIR.glob("*_NO_TRANSCRIPT.json"))

    if not no_transcript_files:
        log.info("No videos need Whisper processing. All good!")
        return

    log.info(f"Found {len(no_transcript_files)} videos to transcribe with Whisper.")
    log.info(f"Loading Whisper model: {WHISPER_MODEL} (this may take a moment) ...")
    model = whisper.load_model(WHISPER_MODEL)

    for i, json_file in enumerate(no_transcript_files, 1):
        with open(json_file, "r", encoding="utf-8") as f:
            video = json.load(f)

        log.info(f"[{i}/{len(no_transcript_files)}] {video['title']}")

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = f"{tmpdir}/audio.mp3"

            if not download_audio(video["url"], audio_path):
                log.warning("  Skipping — audio download failed.")
                continue

            try:
                transcript = transcribe_with_whisper(audio_path, model)
                update_json_file(json_file, transcript)
            except Exception as e:
                log.error(f"  Whisper failed: {e}")


if __name__ == "__main__":
    run()
