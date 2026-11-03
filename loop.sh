#!/usr/bin/env bash
# Every 10 min: rebuild index.html and push, except while timing-sensitive measurements run
# (results_rev/.quiet present). Stops after the final push once revision/DONE exists.
cd "$(dirname "$0")"
STUDY=/c/Users/ggnat/Documents/Claude/2026-10-31/pc_blanket_study
push() {
  python -X utf8 build.py >/dev/null 2>&1
  git add -A index.html data >/dev/null 2>&1
  git diff --cached --quiet || { git commit -q -m "Progress update $(date '+%Y-%m-%d %H:%M')" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" && git push -q origin main; }
}
while true; do
  [ -f "$STUDY/results_rev/.quiet" ] || push
  if [ -f "$STUDY/revision/DONE" ]; then push; break; fi
  sleep 600
done
echo "progress loop finished $(date)"
