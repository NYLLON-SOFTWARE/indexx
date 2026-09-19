#!/usr/bin/env bash
# Quick backlog vs done counts for an INDEXX library root.
# Usage: bash scripts/indexx-status.sh [ROOT]
set -euo pipefail
ROOT="${1:-.}"
ROOT="${ROOT/#\~/$HOME}"
cd "$ROOT"

echo "INDEXX status — $ROOT"
echo

if [[ -f .indexx.json ]]; then
  echo "Config: .indexx.json present"
else
  echo "Config: MISSING .indexx.json (copy examples/.indexx.example.json)"
fi

CAT=""
if [[ -f markdown/instagram/saves-index.md ]]; then
  CAT="markdown/instagram/saves-index.md"
elif [[ -f catalog/instagram-saves.md ]]; then
  CAT="catalog/instagram-saves.md"
fi

if [[ -n "$CAT" ]]; then
  echo "Catalog: $CAT"
  if command -v rg >/dev/null 2>&1; then
    for s in discovered metadata downloaded transcribed wiki_ingested unavailable failed partial; do
      n=$(rg -c "\|[[:space:]]*$s[[:space:]]*\|" "$CAT" 2>/dev/null || true)
      # fallback: count status column occurrences loosely
      n=$(rg -c "$s" "$CAT" 2>/dev/null || echo 0)
      printf "  %-16s %s\n" "$s" "$n"
    done
  else
    echo "  (install ripgrep for status counts: brew install ripgrep)"
  fi
else
  echo "Catalog: not found"
fi

echo
if [[ -d media ]]; then
  echo "Media folders: $(find media -mindepth 3 -maxdepth 3 -type d 2>/dev/null | wc -l | tr -d ' ')"
else
  echo "Media: (none — expected; media stays local and is gitignored)"
fi

echo
if [[ -d wiki/sources ]]; then
  echo "Wiki sources: $(find wiki/sources -name '*.md' 2>/dev/null | wc -l | tr -d ' ')"
else
  echo "Wiki sources: 0"
fi
