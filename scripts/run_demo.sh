#!/usr/bin/env bash
# One-shot demo: install deps → fetch data → run baselines → render leaderboard.
#
# By default the Claude baselines route through your local `claude` CLI
# (Claude Code session) — no API key required. Set OPENAI_API_KEY only if
# you want to compare against gpt-4o.
#
# Usage:
#   ./scripts/run_demo.sh                                      # evidence mode, naive + claude
#   MODE=pdf ./scripts/run_demo.sh                             # full 10-K text mode
#   AGENTS=naive,claude,gpt-4o MODE=pdf LIMIT=5 ./scripts/run_demo.sh

set -euo pipefail

cd "$(dirname "$0")/.."

AGENTS="${AGENTS:-naive,claude}"
LIMIT="${LIMIT:-0}"
MODE="${MODE:-evidence}"

echo "=== Trapstreet eval demo ==="
echo "  agents: $AGENTS"
echo "  mode:   $MODE  $([ "$MODE" = pdf ] && echo '(downloads ~15 PDFs on first run)')"
echo "  limit:  ${LIMIT:-all}"

# --- Auth surface (informational) -----------------------------------------
if command -v claude >/dev/null 2>&1; then
  echo "  auth:   claude CLI ($(claude --version 2>/dev/null | head -1)) — using your Claude Code session"
elif [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "  auth:   ANTHROPIC_API_KEY (no claude CLI on PATH)"
else
  echo
  echo "  ⚠  Neither \`claude\` CLI nor ANTHROPIC_API_KEY is available."
  echo "     Either install Claude Code (https://claude.ai/code) and run \`claude login\`,"
  echo "     or set ANTHROPIC_API_KEY in .env."
fi
echo

# --- Python venv ----------------------------------------------------------
if [[ ! -d .venv ]]; then
  echo "→ Creating .venv…"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# --- Install deps ---------------------------------------------------------
if ! python -c "import anthropic, openai, dotenv, pypdf" >/dev/null 2>&1; then
  echo "→ Installing dependencies…"
  pip install --quiet --upgrade pip
  pip install --quiet -e .
fi

# --- Env (optional — empty file is fine) ----------------------------------
if [[ ! -f .env ]]; then
  cp .env.example .env
fi

# --- Data (FinanceBench questions JSONL) ----------------------------------
./scripts/fetch_financebench.sh

# --- Run ------------------------------------------------------------------
EXTRA=(--mode "$MODE")
if [[ "$LIMIT" != "0" ]]; then
  EXTRA+=(--limit "$LIMIT")
fi

echo
python -m trapstreet_eval.runner compare --agents "$AGENTS" "${EXTRA[@]}"

echo
echo "─────────────────────────────────────────────────────────────"
echo "  scores:  results/compare.md       (open this in your editor)"
echo "  details: results/compare.json     (per-question, per-agent)"
echo "  per-agent breakdowns: results/<agent>.md"
echo "─────────────────────────────────────────────────────────────"
