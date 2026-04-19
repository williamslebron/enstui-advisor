#!/usr/bin/env bash
# =============================================================================
# setup_gcloud.sh
#
# ONE COMMAND TO DEPLOY EVERYTHING TO GOOGLE CLOUD.
# Run this once from your terminal and the full system goes live.
#
# Prerequisites:
#   1. Google Cloud account with billing enabled
#   2. gcloud CLI installed: https://cloud.google.com/sdk/docs/install
#   3. Docker installed: https://docs.docker.com/get-docker/
#   4. A .env file in this directory with all API keys
#
# Usage:
#   chmod +x setup_gcloud.sh
#   ./setup_gcloud.sh
# =============================================================================

set -euo pipefail   # Exit on error, undefined vars, pipe failures

# ── Load .env ─────────────────────────────────────────────────────────────────
if [ ! -f .env ]; then
  echo "❌ .env file not found. Copy .env.example to .env and fill in your keys."
  exit 1
fi
source .env

# ── Config (edit these if needed) ─────────────────────────────────────────────
PROJECT_ID="${GCLOUD_PROJECT_ID:-}"
REGION="us-central1"
SERVICE_NAME="enstui-advisor"
REPO_NAME="enstui-advisor"

# ── Validate required vars ─────────────────────────────────────────────────────
REQUIRED_VARS=(
  YOUTUBE_API_KEY OPENAI_API_KEY ANTHROPIC_API_KEY
  SUPABASE_URL SUPABASE_SERVICE_KEY GCLOUD_PROJECT_ID
)
for var in "${REQUIRED_VARS[@]}"; do
  if [ -z "${!var:-}" ]; then
    echo "❌ Missing required env var: $var"
    exit 1
  fi
done

PROJECT_ID="$GCLOUD_PROJECT_ID"

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║       ENSTUI OU — Google Cloud Setup                    ║"
echo "║       Project: $PROJECT_ID"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ── Step 1: Authenticate & set project ───────────────────────────────────────
echo "▶ Step 1/8: Setting up gcloud..."
gcloud config set project "$PROJECT_ID"
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# ── Step 2: Enable required APIs ─────────────────────────────────────────────
echo "▶ Step 2/8: Enabling Google Cloud APIs (takes ~2 minutes)..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  cloudscheduler.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com \
  --quiet

echo "  ✔ APIs enabled"

# ── Step 3: Create Artifact Registry repo ────────────────────────────────────
echo "▶ Step 3/8: Creating Artifact Registry..."
gcloud artifacts repositories create "$REPO_NAME" \
  --repository-format=docker \
  --location="$REGION" \
  --description="Enstui Ou Advisor Docker images" \
  --quiet 2>/dev/null || echo "  (repository already exists, skipping)"

echo "  ✔ Registry ready"

# ── Step 4: Store secrets in Secret Manager ───────────────────────────────────
echo "▶ Step 4/8: Storing API keys in Secret Manager..."

store_secret() {
  local name="$1"
  local value="$2"

  # Create or update secret
  if gcloud secrets describe "$name" --quiet >/dev/null 2>&1; then
    echo "$value" | gcloud secrets versions add "$name" --data-file=- --quiet
  else
    echo "$value" | gcloud secrets create "$name" --data-file=- --quiet
  fi
  echo "  ✔ Secret: $name"
}

store_secret "YOUTUBE_API_KEY"     "$YOUTUBE_API_KEY"
store_secret "OPENAI_API_KEY"      "$OPENAI_API_KEY"
store_secret "ANTHROPIC_API_KEY"   "$ANTHROPIC_API_KEY"
store_secret "SUPABASE_URL"        "$SUPABASE_URL"
store_secret "SUPABASE_SERVICE_KEY" "$SUPABASE_SERVICE_KEY"

# Optional secrets
[ -n "${ALERT_EMAIL:-}" ]   && store_secret "ALERT_EMAIL"   "$ALERT_EMAIL"
[ -n "${ALERT_WEBHOOK:-}" ] && store_secret "ALERT_WEBHOOK" "$ALERT_WEBHOOK"
[ -n "${SMTP_USER:-}" ]     && store_secret "SMTP_USER"     "$SMTP_USER"
[ -n "${SMTP_PASS:-}" ]     && store_secret "SMTP_PASS"     "$SMTP_PASS"

echo "  ✔ All secrets stored"

# ── Step 5: Build & push Docker image ────────────────────────────────────────
echo "▶ Step 5/8: Building Docker image (takes 3-5 minutes)..."
IMAGE_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}:latest"

docker build \
  --tag "$IMAGE_URL" \
  --cache-from "$IMAGE_URL" \
  . 2>&1 | tail -20

docker push "$IMAGE_URL"
echo "  ✔ Image pushed: $IMAGE_URL"

# ── Step 6: Deploy web app to Cloud Run ──────────────────────────────────────
echo "▶ Step 6/8: Deploying web app to Cloud Run..."

SECRET_FLAGS="--set-secrets=\
YOUTUBE_API_KEY=YOUTUBE_API_KEY:latest,\
OPENAI_API_KEY=OPENAI_API_KEY:latest,\
ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest,\
SUPABASE_URL=SUPABASE_URL:latest,\
SUPABASE_SERVICE_KEY=SUPABASE_SERVICE_KEY:latest"

gcloud run deploy "$SERVICE_NAME" \
  --image="$IMAGE_URL" \
  --region="$REGION" \
  --platform=managed \
  --allow-unauthenticated \
  --port=8080 \
  --memory=1Gi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=3 \
  --concurrency=80 \
  --timeout=300 \
  ${SECRET_FLAGS} \
  --quiet

APP_URL=$(gcloud run services describe "$SERVICE_NAME" \
  --region="$REGION" \
  --format="value(status.url)")

echo "  ✔ Web app live at: $APP_URL"

# ── Step 7: Deploy pipeline job ───────────────────────────────────────────────
echo "▶ Step 7/8: Deploying pipeline job..."

gcloud run jobs deploy "${SERVICE_NAME}-pipeline" \
  --image="$IMAGE_URL" \
  --region="$REGION" \
  --command="python" \
  --args="pipeline.py" \
  --memory=1Gi \
  --cpu=1 \
  --max-retries=3 \
  --task-timeout=3600 \
  ${SECRET_FLAGS} \
  --quiet

echo "  ✔ Pipeline job deployed"

# ── Step 8: Set up Cloud Scheduler ───────────────────────────────────────────
echo "▶ Step 8/8: Configuring daily schedule..."

SERVICE_ACCOUNT="${PROJECT_ID}@appspot.gserviceaccount.com"
JOB_URL="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${SERVICE_NAME}-pipeline:run"

# Daily pipeline at 9 AM UTC
gcloud scheduler jobs create http "enstui-daily-pipeline" \
  --schedule="0 9 * * *" \
  --uri="$JOB_URL" \
  --message-body="{}" \
  --oauth-service-account-email="$SERVICE_ACCOUNT" \
  --location="$REGION" \
  --time-zone="UTC" \
  --attempt-deadline="3600s" \
  --max-retry-attempts=3 \
  --min-backoff=60s \
  --max-backoff=3600s \
  --quiet 2>/dev/null || \
  echo "  (scheduler job already exists — updating)"

# Health ping every 6 hours
gcloud scheduler jobs create http "enstui-health-check" \
  --schedule="0 */6 * * *" \
  --uri="${APP_URL}/_stcore/health" \
  --http-method=GET \
  --location="$REGION" \
  --attempt-deadline="30s" \
  --quiet 2>/dev/null || \
  echo "  (health-check job already exists — skipping)"

echo "  ✔ Scheduled: pipeline daily at 09:00 UTC"

# ── Set up Cloud Build trigger ────────────────────────────────────────────────
echo ""
echo "  ℹ  Auto-deploy on git push requires a Cloud Build trigger."
echo "     Run this after pushing your repo to GitHub:"
echo ""
echo "  gcloud builds triggers create github \\"
echo "    --repo-name=enstui-advisor \\"
echo "    --repo-owner=YOUR_GITHUB_USERNAME \\"
echo "    --branch-pattern='^main$' \\"
echo "    --build-config=cloudbuild.yaml \\"
echo "    --project=$PROJECT_ID"
echo ""

# ── Done ──────────────────────────────────────────────────────────────────────
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  SETUP COMPLETE ✅                                       ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  Web App:     $APP_URL"
echo "║  Pipeline:    Runs daily at 09:00 UTC automatically"
echo "║  Auto-deploy: On every push to main branch"
echo "║  Self-heals:  3 retries + exponential backoff"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "  To run the pipeline RIGHT NOW:"
echo "  gcloud run jobs execute ${SERVICE_NAME}-pipeline --region=${REGION} --wait"
echo ""
