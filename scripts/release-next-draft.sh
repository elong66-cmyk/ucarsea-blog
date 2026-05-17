#!/bin/bash
# release-next-draft.sh — flip the earliest due draft:true post to live, push.
# Runs daily via launchd. One release per run max. Idempotent & safe:
#   - Only touches posts with draft:true AND pubDate <= today
#   - Releases the single earliest-pubDate due draft, then exits
#   - No-op (exit 0) if nothing is due
# Log: scripts/release-log.txt
set -euo pipefail

# launchd runs with a minimal PATH — add Homebrew + system bins
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

REPO="/Volumes/Workspace/projects/ucarsea-blog"
BLOG="$REPO/src/content/blog"
LOG="$REPO/scripts/release-log.txt"
TODAY="$(date +%Y-%m-%d)"

cd "$REPO"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }

# Find earliest-due draft. A file qualifies if it has `draft: true`
# and `pubDate:` <= today. Emit "pubDate<TAB>path" then sort.
candidate=""
candidate_date=""
while IFS= read -r f; do
  grep -q '^draft: true' "$f" || continue
  pd="$(grep -m1 '^pubDate:' "$f" | sed -E 's/pubDate:[[:space:]]*//; s/[[:space:]].*//')"
  [ -z "$pd" ] && continue
  # pubDate <= today ? (string compare works for YYYY-MM-DD)
  if [[ "$pd" > "$TODAY" ]]; then continue; fi
  if [ -z "$candidate_date" ] || [[ "$pd" < "$candidate_date" ]]; then
    candidate="$f"
    candidate_date="$pd"
  fi
done < <(find "$BLOG" -name '*.md' -type f)

if [ -z "$candidate" ]; then
  log "no due draft (today=$TODAY) — no-op"
  exit 0
fi

slug="$(basename "$candidate" .md)"

# Flip draft: true -> draft: false (in-place, macOS sed)
/usr/bin/sed -i '' 's/^draft: true$/draft: false/' "$candidate"

# Sanity: ensure flip happened
if grep -q '^draft: true' "$candidate"; then
  log "ERROR flip failed for $slug — aborting"
  exit 1
fi

# Build to catch any error before pushing
if ! npm run build >/dev/null 2>&1; then
  log "ERROR build failed after flipping $slug — reverting"
  /usr/bin/git checkout -- "$candidate"
  exit 1
fi

/usr/bin/git add "$candidate"
/usr/bin/git commit -m "post: release $slug (scheduled via launchd, pubDate $candidate_date)" >/dev/null 2>&1
if /usr/bin/git push origin >/dev/null 2>&1; then
  log "RELEASED $slug (pubDate=$candidate_date) — pushed OK"
else
  log "ERROR push failed for $slug — committed locally, will retry next run"
  exit 1
fi
