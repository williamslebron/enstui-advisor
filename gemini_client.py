"""
gemini_client.py

Thin shared wrapper around the Google Gen AI SDK so every module in the
project embeds and chats through the same code path.

Models are read from .env with sensible defaults:
    GEMINI_API_KEY         — required
    GEMINI_CHAT_MODEL      — default: gemini-2.5-flash
    GEMINI_EMBED_MODEL     — default: text-embedding-004

pip install google-genai
"""

import os
import logging
from typing import Iterable

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

log = logging.getLogger(__name__)

GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_CHAT_MODEL  = os.getenv("GEMINI_CHAT_MODEL", "gemini-2.5-flash").strip()
GEMINI_EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "text-embedding-004").strip()

# text-embedding-004 produces 768-dim vectors. If you switch to
# gemini-embedding-001 you can request a different dimension, but the
# Supabase schema expects 768, so keep this in sync with supabase_setup.sql.
EMBED_DIMENSION    = 768


def get_gemini_client() -> genai.Client:
    """Return a configured Gemini client. Raises if the key is not set."""
    if not GEMINI_API_KEY:
        raise EnvironmentError(
            "GEMINI_API_KEY is not set in .env — "
            "get one free at https://aistudio.google.com/apikey"
        )
    return genai.Client(api_key=GEMINI_API_KEY)


def embed_texts(client: genai.Client, texts: list[str]) -> list[list[float]]:
    """
    Embed a batch of strings. Returns a list of vectors in the same order
    as the input. Works for any positive batch size.
    """
    if not texts:
        return []

    result = client.models.embed_content(
        model    = GEMINI_EMBED_MODEL,
        contents = texts,
    )

    # The google-genai SDK returns an object with an `embeddings` attribute:
    # a list of ContentEmbedding, each with a `.values` list.
    if hasattr(result, "embeddings") and result.embeddings is not None:
        return [list(e.values) for e in result.embeddings]

    # Fallback for older shape (single embedding)
    if hasattr(result, "embedding") and result.embedding is not None:
        return [list(result.embedding.values)]

    raise RuntimeError(f"Unexpected Gemini embed response shape: {result!r}")


def embed_one(client: genai.Client, text: str) -> list[float]:
    """Convenience: embed a single string."""
    vectors = embed_texts(client, [text])
    return vectors[0]


def generate_text(
    client:         genai.Client,
    user_contents:  list,               # list of {"role": "user"|"model", "parts": [...]}
    system_prompt:  str   = None,
    max_tokens:     int   = 2048,
    temperature:    float = 0.7,
    model:          str   = None,
) -> str:
    """
    Thin wrapper for a single-shot text response from Gemini.
    `user_contents` is a list of role/parts dicts (Gemini conversation format).
    Returns the response text.
    """
    cfg_kwargs = {
        "max_output_tokens": max_tokens,
        "temperature":       temperature,
    }
    if system_prompt:
        cfg_kwargs["system_instruction"] = system_prompt

    response = client.models.generate_content(
        model    = model or GEMINI_CHAT_MODEL,
        contents = user_contents,
        config   = types.GenerateContentConfig(**cfg_kwargs),
    )

    # `.text` is the convenience accessor for the concatenated text parts
    return (response.text or "").strip()


def build_image_part(image_bytes: bytes, mime_type: str = "image/jpeg"):
    """Wrap raw image bytes into a Gemini Part."""
    return types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
