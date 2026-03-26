#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_ROOT="${CODEX_HOME:-$HOME/.codex}/skills"
TARGET_DIR="$TARGET_ROOT/codex-chat-export"

mkdir -p "$TARGET_ROOT"
rm -rf "$TARGET_DIR"
cp -R "$SKILL_DIR" "$TARGET_DIR"

echo "Installed codex-chat-export to $TARGET_DIR"
echo "Invoke it in Codex with \$codex-chat-export"
