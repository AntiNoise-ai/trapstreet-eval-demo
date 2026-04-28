#!/usr/bin/env bash
# Pull the FinanceBench OSS questions JSONL into ./data/financebench/.
# Idempotent: skips if the file is already present.
#
# Data: PatronusAI/FinanceBench, CC-BY-NC-4.0.
#       https://github.com/patronus-ai/financebench

set -euo pipefail

cd "$(dirname "$0")/.."

DATA_DIR="data/financebench/data"
JSONL="$DATA_DIR/financebench_open_source.jsonl"
URL="https://raw.githubusercontent.com/patronus-ai/financebench/main/data/financebench_open_source.jsonl"

if [[ -f "$JSONL" ]]; then
  echo "✓ $JSONL already present ($(wc -l <"$JSONL" | tr -d ' ') records)"
  exit 0
fi

echo "→ Fetching FinanceBench OSS questions (~900KB)…"
mkdir -p "$DATA_DIR"

if command -v curl >/dev/null 2>&1; then
  curl -fsSL "$URL" -o "$JSONL"
elif command -v wget >/dev/null 2>&1; then
  wget -q "$URL" -O "$JSONL"
else
  echo "ERROR: need curl or wget" >&2
  exit 1
fi

LINES=$(wc -l <"$JSONL" | tr -d ' ')
echo "✓ Saved $LINES records to $JSONL"
echo
echo "Note: dataset is licensed CC-BY-NC-4.0 by PatronusAI (non-commercial use)."
echo "      https://huggingface.co/datasets/PatronusAI/financebench"
