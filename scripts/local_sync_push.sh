#!/bin/bash
set -uo pipefail

REPO_DIR="/root/workspace/NS_SalesTracker"
LOG_FILE="$REPO_DIR/cron_sync.log"

exec >> "$LOG_FILE" 2>&1

echo "===== $(date '+%Y-%m-%d %H:%M:%S') Starting local sync ====="

cd "$REPO_DIR" || { echo "Failed to cd into $REPO_DIR"; exit 1; }

git pull --rebase origin main
if [ $? -ne 0 ]; then
    echo "git pull failed, aborting this run."
    exit 1
fi

python3 sync_eshop.py
SYNC_EXIT=$?
if [ $SYNC_EXIT -ne 0 ]; then
    echo "sync_eshop.py exited with code $SYNC_EXIT, skipping commit."
    exit 1
fi

git add database.sqlite docs/data.json

if git diff --staged --quiet; then
    echo "No changes to commit."
else
    git commit -m "Local auto-update database: $(date '+%Y-%m-%d %H:%M:%S')"
    git push origin main
    echo "Committed and pushed changes."
fi

echo "===== $(date '+%Y-%m-%d %H:%M:%S') Finished local sync ====="
echo ""
