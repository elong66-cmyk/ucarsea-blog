#!/bin/bash
# One reviewed post per Beijing day. Never treats a no-op log as publication.
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
REPO="/Volumes/Workspace/projects/ucarsea-blog"
PYTHON="/Volumes/Workspace/projects/ucarsea-leads/.venv/bin/python"
if [ ! -d "$REPO/src/content/blog" ]; then
  echo '{"status":"repository_unavailable","published":false}'
  exit 75
fi
exec "$PYTHON" "$REPO/scripts/release_blog.py" --publish
