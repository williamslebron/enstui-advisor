#!/usr/bin/env bash
# =============================================================================
# deploy.sh — Redeploy after code changes
#
# Use this whenever you update any Python file.
# Rebuilds the image, pushes it, and updates both the web app and pipeline job.
#
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh
# =============================================================================

set -euo pipefail
source .env

PROJECT_ID="$GCLOUD_PROJECT_ID"
REGION="us-central1"
SERVICE_NAME="enstui-advisor"
REPO_NAME="enstui-advisor"
IMAGE_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}:latest"

echo "▶ Building and pushing image..."
docker build --tag "$IMAGE_URL" --cache-from "$IMAGE_URL" . 2>&1 | tail -10
docker push "$IMAGE_URL"

echo "▶ Updating web app..."
gcloud run deploy "$SERVICE_NAME" \
  --image="$IMAGE_URL" \
  --region="$REGION" \
  --quiet

echo "▶ Updating pipeline job..."
gcloud run jobs update "${SERVICE_NAME}-pipeline" \
  --image="$IMAGE_URL" \
  --region="$REGION" \
  --quiet

APP_URL=$(gcloud run services describe "$SERVICE_NAME" \
  --region="$REGION" \
  --format="value(status.url)")

echo "✅ Redeployed. Live at: $APP_URL"
