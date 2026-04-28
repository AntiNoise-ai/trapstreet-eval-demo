#!/usr/bin/env bash
# Install the trapstreet-eval Claude Code skill — places three files under
# ~/.claude/skills/trapstreet-eval/. After install, run /trapstreet-eval in
# any Claude Code session.
#
# One-liner:
#   curl -fsSL https://raw.githubusercontent.com/AntiNoise-ai/trapstreet-eval-demo/main/skill/install.sh | bash
#
# Or, if you cloned the repo:
#   ./skill/install.sh

set -euo pipefail

DEST="$HOME/.claude/skills/trapstreet-eval"
BASE_URL="${TRAPSTREET_INSTALL_BASE:-https://raw.githubusercontent.com/AntiNoise-ai/trapstreet-eval-demo/main/skill/trapstreet-eval}"

mkdir -p "$DEST"

# If running from a local clone, copy from sibling dir; otherwise curl.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_SRC="$SCRIPT_DIR/trapstreet-eval"

if [[ -d "$LOCAL_SRC" ]]; then
  echo "→ Installing from local clone: $LOCAL_SRC"
  cp "$LOCAL_SRC/SKILL.md"      "$DEST/SKILL.md"
  cp "$LOCAL_SRC/questions.json" "$DEST/questions.json"
  cp "$LOCAL_SRC/grade.py"       "$DEST/grade.py"
else
  echo "→ Downloading from $BASE_URL"
  for f in SKILL.md questions.json grade.py; do
    if command -v curl >/dev/null 2>&1; then
      curl -fsSL "$BASE_URL/$f" -o "$DEST/$f"
    elif command -v wget >/dev/null 2>&1; then
      wget -q "$BASE_URL/$f" -O "$DEST/$f"
    else
      echo "ERROR: need curl or wget" >&2
      exit 1
    fi
  done
fi

chmod +x "$DEST/grade.py"

echo
echo "✓ Installed to $DEST"
echo "  Run /trapstreet-eval in any Claude Code session."
