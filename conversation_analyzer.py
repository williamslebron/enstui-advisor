"""
conversation_analyzer.py

Analyzes screenshots of text conversations using Gemini Vision.
Identifies power dynamics, mistakes, her interest level, and
produces a full action plan with exact timing.
"""

import json
import logging
from dotenv import load_dotenv
from google.genai import types

from gemini_client import get_gemini_client, build_image_part, GEMINI_CHAT_MODEL
from retriever import search, format_context_for_llm, get_clients

load_dotenv()

log = logging.getLogger(__name__)


# ── Image helpers ─────────────────────────────────────────────────────────────

def detect_media_type(filename: str) -> str:
    ext = filename.lower().split(".")[-1]
    return {
        "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "png": "image/png",  "gif": "image/gif",
        "webp": "image/webp"
    }.get(ext, "image/jpeg")


# ── Analysis prompt ───────────────────────────────────────────────────────────

ANALYSIS_SYSTEM_PROMPT = """
You are the Enstui Ou Strategic Conversation Analyst.
You analyze real text conversation screenshots with clinical precision.

Your analysis framework is based entirely on Enstui Ou's teachings:
- "Teknik Zonbifye": Is she addicted, curious, or pulling away?
- "Belle Mots": Are the messages poetic and powerful, or weak and desperate?
- "King Mindset": Is the man leading or chasing?
- Response timing patterns: What do her delays reveal?
- Emoji/tone analysis: What is she actually communicating vs what she types?

CONTEXT FROM ENSTUI OU KNOWLEDGE BASE:
{rag_context}

OUTPUT FORMAT — always respond in this exact JSON structure:
{{
  "power_score": <integer 1-10, 10 = man has total frame control>,
  "her_interest_level": "<HIGH / MEDIUM / LOW / FADING>",
  "overall_verdict": "<one brutal honest sentence about where he stands>",
  "timeline": [
    {{
      "moment": "<description of specific message or exchange>",
      "what_happened": "<what he did>",
      "impact": "<GAINED_VALUE | LOST_VALUE | NEUTRAL>",
      "why": "<technique name from Enstui Ou + explanation>"
    }}
  ],
  "critical_mistakes": [
    {{
      "mistake": "<what he did wrong>",
      "technique_violated": "<which Enstui Ou principle this breaks>",
      "severity": "<LOW | MEDIUM | HIGH | CRITICAL>"
    }}
  ],
  "what_she_is_doing": "<her strategy — is she testing, pulling away, playing games, genuinely interested?>",
  "his_current_position": "<is he in a position of value or has he lost frame?>",
  "action_plan": [
    {{
      "step": 1,
      "action": "<exactly what to do>",
      "message_option_a": "<Direct approach message — if applicable>",
      "message_option_b": "<Mystery/Zonbifye approach message — if applicable>",
      "timing": "<exact timing: 'Send at 9PM tonight', 'Wait 48 hours', 'Send immediately'>",
      "why": "<which Enstui Ou technique and why this works>"
    }}
  ],
  "overall_strategy": "<2-3 sentence summary of the complete strategy going forward>"
}}

Be brutal and honest. Do not sugarcoat. If he is simping, say so directly.
"""


# ── Core analyzer ─────────────────────────────────────────────────────────────

class ConversationAnalyzer:

    def __init__(self):
        self.client                   = get_gemini_client()
        self.ai_client, self.supabase = get_clients()

    def _get_rag_context(self, context_hint: str = "") -> str:
        query = f"conversation analysis power dynamic texting strategy {context_hint}"
        try:
            results = search(
                query,
                match_count     = 6,
                match_threshold = 0.35,
                ai_client       = self.ai_client,
                supabase        = self.supabase
            )
            return format_context_for_llm(results)
        except Exception:
            return "Knowledge base temporarily unavailable."

    def analyze(
        self,
        images:       list[tuple[bytes, str]],
        user_context: str = "",
        goal:         str = ""
    ) -> dict:
        if not images:
            raise ValueError("No images provided")

        rag_ctx = self._get_rag_context(user_context)
        system  = ANALYSIS_SYSTEM_PROMPT.format(rag_context=rag_ctx)

        # Build the user content: image part(s) + text instructions
        parts = []
        for img_bytes, filename in images:
            mime = detect_media_type(filename)
            parts.append(build_image_part(img_bytes, mime))

        intro_text = "Analyze this text conversation screenshot(s) using the Enstui Ou framework.\n"
        if user_context:
            intro_text += f"\nContext from the user: {user_context}\n"
        if goal:
            intro_text += f"User's goal: {goal}\n"
        intro_text += "\nProvide the full JSON analysis."
        parts.append({"text": intro_text})

        response = self.client.models.generate_content(
            model    = GEMINI_CHAT_MODEL,
            contents = [{"role": "user", "parts": parts}],
            config   = types.GenerateContentConfig(
                system_instruction  = system,
                max_output_tokens   = 3000,
                temperature         = 0.6,
                response_mime_type  = "application/json",
            ),
        )

        raw = (response.text or "").strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            log.warning("Could not parse JSON from analysis — returning raw")
            return {"raw_analysis": raw, "parse_error": True}
