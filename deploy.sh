#!/usr/bin/env bash
# Deploy RepoSage to Cloud Run. Run from the repository root (Cloud Shell works).
#
#   export GOOGLE_API_KEY=...   # never write the key into a file in this repo
#   ./deploy.sh
set -euo pipefail

: "${GOOGLE_API_KEY:?Set GOOGLE_API_KEY in your environment first}"
REGION="${REGION:-asia-south1}"

# --max-instances 1: the index lives in memory (docs/adr/0003).
gcloud run deploy reposage \
  --source . \
  --region "$REGION" \
  --max-instances 1 \
  --memory 2Gi \
  --timeout 120 \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_API_KEY=${GOOGLE_API_KEY}"
