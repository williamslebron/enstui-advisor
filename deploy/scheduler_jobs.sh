# ── Cloud Scheduler Jobs ─────────────────────────────────────────────────────
# These are created automatically by setup_gcloud.sh.
# Listed here for documentation and manual recovery.

# Job 1: Daily pipeline (scrape + embed)
# Runs at 9:00 AM UTC every day
# gcloud scheduler jobs create http enstui-daily-pipeline \
#   --schedule="0 9 * * *" \
#   --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${SERVICE_NAME}-pipeline:run" \
#   --message-body="{}" \
#   --oauth-service-account-email="${SERVICE_ACCOUNT}" \
#   --location="${REGION}" \
#   --time-zone="UTC" \
#   --attempt-deadline="3600s" \
#   --max-retry-attempts=3 \
#   --min-backoff=60s \
#   --max-backoff=3600s

# Job 2: Health check ping (every 6 hours)
# Makes sure the web app is alive
# gcloud scheduler jobs create http enstui-health-check \
#   --schedule="0 */6 * * *" \
#   --uri="${APP_URL}/_stcore/health" \
#   --http-method=GET \
#   --location="${REGION}" \
#   --attempt-deadline="30s"
