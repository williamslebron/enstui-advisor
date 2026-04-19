# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Enstui Ou — Command Runner
#  Usage: make <command>
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PYTHON = .venv/bin/python
PIP    = .venv/bin/pip

# Default: show help
.DEFAULT_GOAL := help

.PHONY: help setup heal check status run scrape embed books whisper open-env

# ── Help ──────────────────────────────────────────────────
help:
	@echo ""
	@echo "  ┌─────────────────────────────────────────────┐"
	@echo "  │   ENSTUI OU — Strategic Advisor System      │"
	@echo "  └─────────────────────────────────────────────┘"
	@echo ""
	@echo "  SETUP"
	@echo "    make setup      First-time install (run once)"
	@echo "    make open-env   Open .env in editor to add API keys"
	@echo ""
	@echo "  HEALTH"
	@echo "    make check      Health check + auto-heal"
	@echo "    make heal       Force full environment reset"
	@echo "    make status     Show system status dashboard"
	@echo ""
	@echo "  PIPELINE"
	@echo "    make scrape     Step 1 — Pull videos from YouTube"
	@echo "    make embed      Step 2 — Embed transcripts to Supabase"
	@echo "    make books      Step 2b — Embed PDFs from books/"
	@echo "    make whisper    Transcribe no-caption videos (needs ffmpeg)"
	@echo "    make pipeline   Run scrape + embed in sequence"
	@echo ""
	@echo "  APP"
	@echo "    make run        Launch the Streamlit advisor app"
	@echo ""

# ── Setup ─────────────────────────────────────────────────
setup:
	python setup_and_run.py --setup

# ── Health & Healing ──────────────────────────────────────
check:
	python setup_and_run.py --check-only

heal:
	python setup_and_run.py --heal

status:
	python setup_and_run.py --status

# ── Open .env ─────────────────────────────────────────────
open-env:
	@if [ -f .env ]; then \
		code .env; \
	else \
		cp .env.example .env && code .env; \
	fi

# ── Pipeline ──────────────────────────────────────────────
scrape:
	@python setup_and_run.py --check-only || python setup_and_run.py --heal
	python setup_and_run.py --run-scraper

embed:
	@python setup_and_run.py --check-only || python setup_and_run.py --heal
	python setup_and_run.py --run-embed

books:
	@python setup_and_run.py --check-only || python setup_and_run.py --heal
	python setup_and_run.py --run-books

whisper:
	@python setup_and_run.py --check-only || python setup_and_run.py --heal
	$(PYTHON) whisper_fallback.py

pipeline: scrape embed
	@echo "Full pipeline complete."

# ── App ───────────────────────────────────────────────────
run:
	@python setup_and_run.py --check-only || python setup_and_run.py --heal
	streamlit run app.py
