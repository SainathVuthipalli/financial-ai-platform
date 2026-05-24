#!/bin/bash
set -e

# Write GCP service account JSON from env var to a temp file so BigQuery works on Railway
if [ -n "$GOOGLE_APPLICATION_CREDENTIALS_JSON" ]; then
    echo "$GOOGLE_APPLICATION_CREDENTIALS_JSON" > /tmp/gcp-credentials.json
    export GOOGLE_APPLICATION_CREDENTIALS=/tmp/gcp-credentials.json
fi

exec uvicorn dashboard.main:app --host 0.0.0.0 --port "${PORT:-8000}"
