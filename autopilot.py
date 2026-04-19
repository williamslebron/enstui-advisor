"""
autopilot.py

The Autopilot Campaign Manager.
When the user leaves, this system generates a full timed message
sequence based on Enstui Ou strategy, stores it locally, and
optionally sends messages via Twilio SMS/WhatsApp automatically.

Campaign generation is powered by Gemini.
"""

import os
import json
import time
import logging
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from google.genai import types

from gemini_client import get_gemini_client, GEMINI_CHAT_MODEL
from retriever import search, format_context_for_llm, get_clients

load_dotenv()

TWILIO_SID   = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM  = os.getenv("TWILIO_FROM_NUMBER", "")

log = logging.getLogger(__name__)

CAMPAIGNS_FILE = Path("campaigns.json")


# ── Campaign data model ───────────────────────────────────────────────────────

def load_campaigns() -> list:
    if CAMPAIGNS_FILE.exists():
        return json.loads(CAMPAIGNS_FILE.read_text())
    return []

def save_campaigns(campaigns: list):
    CAMPAIGNS_FILE.write_text(json.dumps(campaigns, indent=2, ensure_ascii=False))

def get_campaign(campaign_id: str) -> dict | None:
    return next((c for c in load_campaigns() if c["id"] == campaign_id), None)

def update_campaign(campaign_id: str, updates: dict):
    campaigns = load_campaigns()
    for c in campaigns:
        if c["id"] == campaign_id:
            c.update(updates)
    save_campaigns(campaigns)


# ── Campaign generator (Gemini) ───────────────────────────────────────────────

CAMPAIGN_SYSTEM = """
You are the Enstui Ou Autopilot Strategist.
Your job is to generate a complete timed message campaign based on the
user's situation, goal, and Enstui Ou's techniques.

CONTEXT FROM KNOWLEDGE BASE:
{rag_context}

You must output ONLY valid JSON in this exact structure:
{{
  "campaign_name": "<short name for this campaign>",
  "strategy_summary": "<2 sentences: what overall approach and why>",
  "messages": [
    {{
      "step": 1,
      "delay_hours": <number — hours from NOW to send this>,
      "message_text": "<the exact message to send>",
      "technique": "<Enstui Ou technique name used>",
      "purpose": "<what this message is designed to achieve>",
      "send_at_label": "<human label like 'Tonight 9PM' or 'Tomorrow evening'>"
    }}
  ],
  "rules_while_away": [
    "<rule 1 — e.g. Do NOT double text if she doesn't reply>",
    "<rule 2>",
    "<rule 3>"
  ],
  "abort_conditions": [
    "<condition that should STOP the campaign — e.g. She initiates contact first>"
  ]
}}

Strategy rules:
- Never more than 5 messages in a campaign
- Minimum 4 hours between messages
- Messages get shorter and more confident as the campaign progresses
- Apply Push-Pull, Mystery, and Silence as the Enstui Ou teachings direct
- If the situation is critical (she's pulling away hard), start with silence, not contact
"""


class AutopilotManager:

    def __init__(self):
        self.client                   = get_gemini_client()
        self.ai_client, self.supabase = get_clients()
        self._scheduler_thread        = None
        self._running                 = False

    def _get_rag_context(self, situation: str) -> str:
        try:
            results = search(
                f"texting strategy campaign {situation}",
                match_count     = 5,
                match_threshold = 0.35,
                ai_client       = self.ai_client,
                supabase        = self.supabase
            )
            return format_context_for_llm(results)
        except Exception:
            return ""

    def generate_campaign(
        self,
        situation:     str,
        goal:          str,
        her_name:      str = "her",
        analysis_data: dict = None
    ) -> dict:
        rag_ctx = self._get_rag_context(situation)
        system  = CAMPAIGN_SYSTEM.format(rag_context=rag_ctx)

        context_block = f"SITUATION: {situation}\nGOAL: {goal}\nHER NAME: {her_name}\n"
        if analysis_data and not analysis_data.get("parse_error"):
            context_block += (
                f"CURRENT POWER SCORE: {analysis_data.get('power_score', 'unknown')}/10\n"
                f"HER INTEREST LEVEL: {analysis_data.get('her_interest_level', 'unknown')}\n"
                f"VERDICT: {analysis_data.get('overall_verdict', '')}\n"
                f"HER STRATEGY: {analysis_data.get('what_she_is_doing', '')}\n"
            )

        response = self.client.models.generate_content(
            model    = GEMINI_CHAT_MODEL,
            contents = [{
                "role":  "user",
                "parts": [{"text": context_block + "\nGenerate the campaign JSON."}]
            }],
            config   = types.GenerateContentConfig(
                system_instruction  = system,
                max_output_tokens   = 2000,
                temperature         = 0.7,
                response_mime_type  = "application/json",
            ),
        )

        raw = (response.text or "").strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        campaign_data = json.loads(raw)

        now = datetime.now(timezone.utc)
        for msg in campaign_data.get("messages", []):
            send_time = now + timedelta(hours=msg["delay_hours"])
            msg["send_at_iso"] = send_time.isoformat()
            msg["status"]      = "pending"

        import uuid
        campaign = {
            "id":           str(uuid.uuid4())[:8],
            "her_name":     her_name,
            "situation":    situation,
            "goal":         goal,
            "created_at":   now.isoformat(),
            "status":       "active",
            "sms_enabled":  bool(TWILIO_SID and TWILIO_TOKEN and TWILIO_FROM),
            "to_number":    "",
            **campaign_data
        }

        campaigns = load_campaigns()
        campaigns.append(campaign)
        save_campaigns(campaigns)

        log.info(f"Campaign created: {campaign['id']} — {len(campaign_data.get('messages',[]))} messages")
        return campaign

    def pause_campaign(self, campaign_id: str):
        update_campaign(campaign_id, {"status": "paused"})
        log.info(f"Campaign {campaign_id} paused")

    def resume_campaign(self, campaign_id: str):
        update_campaign(campaign_id, {"status": "active"})
        log.info(f"Campaign {campaign_id} resumed")

    def abort_campaign(self, campaign_id: str):
        update_campaign(campaign_id, {"status": "aborted"})
        log.info(f"Campaign {campaign_id} aborted")

    def skip_message(self, campaign_id: str, step: int):
        campaigns = load_campaigns()
        for c in campaigns:
            if c["id"] == campaign_id:
                for msg in c.get("messages", []):
                    if msg["step"] == step:
                        msg["status"] = "skipped"
        save_campaigns(campaigns)

    def send_via_twilio(self, to_number: str, message_text: str) -> dict:
        if not (TWILIO_SID and TWILIO_TOKEN and TWILIO_FROM):
            return {"success": False, "error": "Twilio not configured"}
        try:
            from twilio.rest import Client
            tw_client = Client(TWILIO_SID, TWILIO_TOKEN)
            msg = tw_client.messages.create(
                body = message_text,
                from_= TWILIO_FROM,
                to   = to_number
            )
            return {"success": True, "sid": msg.sid}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def tick(self):
        now       = datetime.now(timezone.utc)
        campaigns = load_campaigns()
        changed   = False

        for campaign in campaigns:
            if campaign["status"] != "active":
                continue

            for msg in campaign.get("messages", []):
                if msg["status"] != "pending":
                    continue

                send_at = datetime.fromisoformat(msg["send_at_iso"])
                if now >= send_at:
                    log.info(f"[Campaign {campaign['id']}] Sending step {msg['step']}: {msg['message_text'][:40]}...")

                    if campaign.get("sms_enabled") and campaign.get("to_number"):
                        result = self.send_via_twilio(campaign["to_number"], msg["message_text"])
                        msg["send_result"] = result
                        if result["success"]:
                            msg["status"]  = "sent"
                            msg["sent_at"] = now.isoformat()
                            log.info(f"  ✔ Sent via Twilio (SID: {result.get('sid')})")
                        else:
                            log.error(f"  ✘ Twilio error: {result.get('error')}")
                    else:
                        msg["status"]   = "ready_to_send"
                        msg["ready_at"] = now.isoformat()

                    changed = True

            statuses = [m["status"] for m in campaign.get("messages", [])]
            if all(s in ("sent", "skipped", "ready_to_send") for s in statuses):
                campaign["status"] = "completed"
                log.info(f"Campaign {campaign['id']} completed")
                changed = True

        if changed:
            save_campaigns(campaigns)

    def start_background_scheduler(self, interval_seconds: int = 60):
        if self._running:
            return

        self._running = True

        def loop():
            while self._running:
                try:
                    self.tick()
                except Exception as e:
                    log.error(f"Scheduler tick error: {e}")
                time.sleep(interval_seconds)

        self._scheduler_thread = threading.Thread(target=loop, daemon=True)
        self._scheduler_thread.start()
        log.info("Autopilot scheduler started (background thread)")

    def stop_background_scheduler(self):
        self._running = False
