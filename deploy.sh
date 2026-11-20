#!/usr/bin/env bash
# Deploy RepoSage to Cloud Run. Run from the repository root (Cloud Shell works).
#
# Two ways to reach Gemini:
#
#   Vertex AI (default, no API key): the Cloud Run service account calls Vertex.
#   It needs the Vertex AI API enabled and the role roles/aiplatform.user on that
#   service account. Usage is billed to your Google Cloud billing account.
#       ./deploy.sh
#
#   AI Studio API key: set GOOGLE_API_KEY in your shell first (never in a file
#   in this repository).
#       export GOOGLE_API_KEY=...
#       ./deploy.sh
set -euo pipefail

REGION="${REGION:-asia-south1}"
PROJECT="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
MODEL="${GEMINI_MODEL:-gemini-3.5-flash-lite}"
: "${PROJECT:?No project set. Run: gcloud config set project YOUR_PROJECT_ID}"

if [ -n "${GOOGLE_API_KEY:-}" ]; then
  ENV_VARS="GOOGLE_API_KEY=${GOOGLE_API_KEY},GEMINI_MODEL=${MODEL}"
  echo "Using the AI Studio API key from your environment."
else
  # Gemini 3.x models are served from the "global" Vertex location.
  ENV_VARS="GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=${PROJECT},GOOGLE_CLOUD_LOCATION=global,GEMINI_MODEL=${MODEL}"
  echo "Using Vertex AI in project ${PROJECT} (no API key)."
fi

# --max-instances 1: the index lives in memory (docs/adr/0003).
gcloud run deploy reposage \
  --source . \
  --project "$PROJECT" \
  --region "$REGION" \
  --max-instances 1 \
  --memory 2Gi \
  --timeout 300 \
  --allow-unauthenticated \
  --set-env-vars "$ENV_VARS"
