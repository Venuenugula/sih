#!/usr/bin/env bash
# Run INDUSAI for LAN or VPS access (bind all interfaces).
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -d .venv ]]; then
  echo "Create a venv first: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

if [[ ! -f .env ]]; then
  echo "Copy .env.example to .env and set LLM_API_KEY before deploying."
  exit 1
fi

exec streamlit run app.py \
  --server.address=0.0.0.0 \
  --server.port="${PORT:-8501}" \
  --server.headless=true \
  --browser.gatherUsageStats=false
