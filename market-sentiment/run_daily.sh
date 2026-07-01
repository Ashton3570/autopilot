#!/bin/bash
# Daily runner for the Market Sentiment Brief. Point your cron/launchd at this.
# Logs to logs/<date>.log and (optionally) opens the brief.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
mkdir -p logs
DATE="$(date +%Y-%m-%d)"

# Load secrets if you keep them in a local .env (ANTHROPIC_API_KEY, REDDIT_*)
[ -f "$DIR/.env" ] && set -a && . "$DIR/.env" && set +a

python3 brief.py "$@" >> "logs/$DATE.log" 2>&1
echo "done -> briefs/$DATE-sentiment-brief.html"
