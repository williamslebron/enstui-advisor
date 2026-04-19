"""
advisor.py

Step 3 — The AI Brain.
Combines RAG retrieval from Supabase with the Gemini API to act as the
Enstui Ou Strategic Advisor.

Used as a module by app.py, or tested standalone:
    python advisor.py
"""

import os
import logging
from dotenv import load_dotenv
from google.genai import types

from gemini_client import get_gemini_client, GEMINI_CHAT_MODEL
from retriever import search, format_context_for_llm, get_clients, get_source_stats

load_dotenv()

log = logging.getLogger(__name__)

# ── System Prompt ─────────────────────────────────────────────────────────────

BASE_SYSTEM_PROMPT = """
You are the Lead Strategic Advisor representing the philosophy and techniques
of the YouTube channel "Enstui Ou" (@EnstuiOu).

Your mission is to help the user navigate social situations, dating, and text
conversations with the confidence, mystery, and strategy taught by the channel.

══════════════════════════════════════════════════════
KNOWLEDGE BASE  (retrieved live from videos + books)
══════════════════════════════════════════════════════
{rag_context}

══════════════════════════════════════════════════════
CORE PHILOSOPHY
══════════════════════════════════════════════════════
- The "King Mindset": High-value men lead, they do not chase.
- "Belle Mots": Strategic, poetic language that triggers emotional responses.
- "Teknik Zonbifye": Creating curiosity and psychological addiction in her mind.
- "Teknik 2 Segonn": The 2-second rule — decisive, confident action.
- "Kijan pouw jere yon fi": How to handle a woman at every stage.

══════════════════════════════════════════════════════
RESPONSE STRUCTURE (use for every SITUATION given)
══════════════════════════════════════════════════════
1. POWER DYNAMIC ANALYSIS
   Is the user gaining or losing value? Be direct. No sugarcoating.

2. THREE MESSAGE OPTIONS
   Option A — "The Direct Approach": High confidence, clear intent.
   Option B — "The Mystery Approach": Triggers Zonbifye (curiosity/obsession).
   Option C — "The Push-Pull": Use when she is cold or pulling away.

3. THE WHY + TIMING
   - Name the technique and which video/book it comes from.
   - Give EXACT timing: "Send at 9 PM", "Wait 4 hours", "Send immediately."

══════════════════════════════════════════════════════
TONE RULES
══════════════════════════════════════════════════════
- Confident and masculine. Never validate desperation.
- English for explanations. Haitian Creole terms used naturally.
- If the user sounds like they're simping — call it out directly.
- Short, powerful sentences. No filler.

══════════════════════════════════════════════════════
WHEN NO SITUATION IS PROVIDED YET
══════════════════════════════════════════════════════
Ask clearly for:
  1. The Situation — what just happened?
  2. The Goal — what outcome do you want?
  3. The Evidence — paste the last text message sent or received.
"""


# ── Advisor Class ─────────────────────────────────────────────────────────────

class EnstuiAdvisor:
    """
    Stateful advisor that maintains full conversation history
    and retrieves fresh RAG context on every user message.
    """

    def __init__(self):
        self.client                   = get_gemini_client()
        self.ai_client, self.supabase = get_clients()   # ai_client is Gemini too
        self.conversation             = []              # [{role, content}]
        self._log_db_stats()

    def _log_db_stats(self):
        try:
            stats = get_source_stats(self.supabase)
            log.info(
                f"Knowledge base ready — "
                f"{len(stats['videos'])} videos, "
                f"{len(stats['books'])} books, "
                f"{stats['total_chunks']} chunks"
            )
        except Exception as e:
            log.warning(f"Could not load DB stats: {e}")

    def _build_search_query(self, user_message: str) -> str:
        recent = ""
        user_turns = [m for m in self.conversation if m["role"] == "user"]
        if len(user_turns) >= 2:
            # Previous user turn (exclude the one we just appended)
            recent = user_turns[-2]["content"][:200]
        return f"{user_message} {recent}".strip()

    def _get_system_prompt(self, user_message: str) -> str:
        try:
            query   = self._build_search_query(user_message)
            results = search(
                query,
                match_count     = 8,
                match_threshold = 0.40,
                ai_client       = self.ai_client,
                supabase        = self.supabase
            )
            context = format_context_for_llm(results)
            log.info(f"RAG: {len(results)} chunks retrieved")
        except Exception as e:
            log.warning(f"RAG failed: {e} — continuing without context.")
            context = "Knowledge base temporarily unavailable."

        return BASE_SYSTEM_PROMPT.format(rag_context=context)

    def _to_gemini_contents(self) -> list:
        """
        Convert the stored conversation history (user/assistant) into the
        role/parts format Gemini expects (user/model).
        """
        contents = []
        for turn in self.conversation:
            role = "user" if turn["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": turn["content"]}]})
        return contents

    def chat(self, user_message: str) -> str:
        """
        Send a user message, get an advisor response.
        Maintains full multi-turn history.
        """
        self.conversation.append({"role": "user", "content": user_message})

        system_prompt = self._get_system_prompt(user_message)

        response = self.client.models.generate_content(
            model    = GEMINI_CHAT_MODEL,
            contents = self._to_gemini_contents(),
            config   = types.GenerateContentConfig(
                system_instruction = system_prompt,
                max_output_tokens  = 2048,
                temperature        = 0.8,
            ),
        )

        reply = (response.text or "").strip()
        if not reply:
            reply = "[The advisor returned an empty response. Try again.]"

        self.conversation.append({"role": "assistant", "content": reply})
        return reply

    def reset(self):
        self.conversation = []

    @property
    def message_count(self) -> int:
        return len([m for m in self.conversation if m["role"] == "user"])


# ── Terminal Test Mode ────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    print("\n" + "═" * 60)
    print("  ENSTUI OU — Strategic Advisor  (Terminal Mode, Gemini)")
    print("  Commands:  reset | quit")
    print("═" * 60 + "\n")

    advisor  = EnstuiAdvisor()
    greeting = advisor.chat("Introduce yourself briefly and ask me for my situation.")
    print(f"🎯 Advisor:\n{greeting}\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
            break

        if not user_input:
            continue
        if user_input.lower() == "quit":
            print("Session ended.")
            break
        if user_input.lower() == "reset":
            advisor.reset()
            print("— Conversation cleared —\n")
            continue

        try:
            print(f"\n🎯 Advisor:\n{advisor.chat(user_input)}\n")
        except Exception as e:
            print(f"\n⚠️  Error: {e}\n")
