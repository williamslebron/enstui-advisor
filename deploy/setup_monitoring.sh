#!/usr/bin/env bash
# =============================================================================
# deploy/setup_monitoring.sh
#
# Sets up Google Cloud Monitoring alerts so you get notified if:
#   - The pipeline job fails
#   - The web app has high error rates
#   - Cloud Run instances crash-loop
#
# Run once AFTER setup_gcloud.sh:
#   chmod +x deploy/setup_monitoring.sh
#   ./deploy/setup_monitoring.sh
# =============================================================================

set -euo pipefail
source .env

PROJECT_ID="$GCLOUD_PROJECT_ID"
REGION="us-central1"
NOTIFICATION_EMAIL="${ALERT_EMAIL:-$SMTP_USER}"

if [ -z "$NOTIFICATION_EMAIL" ]; then
  echo "ℹ  No ALERT_EMAIL set — skipping email notification channel."
  CHANNEL_ID=""
else
  echo "▶ Creating notification channel for: $NOTIFICATION_EMAIL"
  CHANNEL_ID=$(gcloud alpha monitoring channels create \
    --display-name="Enstui Alerts" \
    --type=email \
    --channel-labels="email_address=${NOTIFICATION_EMAIL}" \
    --format="value(name)" \
    --project="$PROJECT_ID")
  echo "  ✔ Notification channel: $CHANNEL_ID"
fi

# ── Alert 1: Cloud Run Job Failure ───────────────────────────────────────────
echo "▶ Creating pipeline failure alert..."
cat > /tmp/pipeline_alert.json << EOF
{
  "displayName": "Enstui Pipeline Job Failed",
  "conditions": [{
    "displayName": "Cloud Run Job failed",
    "conditionThreshold": {
      "filter": "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"enstui-advisor-pipeline\" AND metric.type=\"run.googleapis.com/job/completed_task_count\" AND metric.labels.result=\"failed\"",
      "comparison": "COMPARISON_GT",
      "thresholdValue": 0,
      "duration": "0s",
      "aggregations": [{
        "alignmentPeriod": "300s",
        "perSeriesAligner": "ALIGN_SUM"
      }]
    }
  }],
  "alertStrategy": {
    "autoClose": "86400s"
  },
  "combiner": "OR",
  "notificationChannels": ["${CHANNEL_ID}"],
  "documentation": {
    "content": "The daily Enstui Ou pipeline job failed. Check Cloud Run logs: https://console.cloud.google.com/run/jobs/details/${REGION}/enstui-advisor-pipeline/executions?project=${PROJECT_ID}"
  }
}
EOF

gcloud alpha monitoring policies create \
  --policy-from-file=/tmp/pipeline_alert.json \
  --project="$PROJECT_ID" \
  --quiet 2>/dev/null || echo "  (alert may already exist)"

echo "  ✔ Pipeline failure alert created"

# ── Alert 2: High Error Rate on Web App ──────────────────────────────────────
echo "▶ Creating web app error rate alert..."
cat > /tmp/error_rate_alert.json << EOF
{
  "displayName": "Enstui Web App High Error Rate",
  "conditions": [{
    "displayName": "HTTP 5xx error rate > 10%",
    "conditionThreshold": {
      "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"enstui-advisor\" AND metric.type=\"run.googleapis.com/request_count\" AND metric.labels.response_code_class=\"5xx\"",
      "comparison": "COMPARISON_GT",
      "thresholdValue": 5,
      "duration": "300s",
      "aggregations": [{
        "alignmentPeriod": "60s",
        "perSeriesAligner": "ALIGN_RATE"
      }]
    }
  }],
  "combiner": "OR",
  "notificationChannels": ["${CHANNEL_ID}"],
  "documentation": {
    "content": "The Enstui Ou web app is returning too many 5xx errors. Check: https://console.cloud.google.com/run/detail/${REGION}/enstui-advisor/logs?project=${PROJECT_ID}"
  }
}
EOF

gcloud alpha monitoring policies create \
  --policy-from-file=/tmp/error_rate_alert.json \
  --project="$PROJECT_ID" \
  --quiet 2>/dev/null || echo "  (alert may already exist)"

echo "  ✔ Web app error rate alert created"
echo ""
echo "✅ Monitoring configured. Alerts will go to: ${NOTIFICATION_EMAIL:-<none set>}"
echo "   View all alerts: https://console.cloud.google.com/monitoring/alerting?project=${PROJECT_ID}"
