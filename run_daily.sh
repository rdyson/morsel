#!/bin/bash
#
# Daily podcast digest generation.
# Meant to be run by cron at 7am GMT.
#
# 1. Polls AgentMail for any remaining unprocessed emails
# 2. Generates the digest from yesterday's queue
# 3. Uploads audio + feed to storage
# 4. Cleans up old episodes from storage
#
# Crontab entry (7am GMT):
#   0 7 * * * /home/openclaw/morsel/run_daily.sh >> /home/openclaw/morsel/data/cron.log 2>&1

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

source venv/bin/activate

echo "========================================"
echo "  Morsel — $(date -u '+%Y-%m-%d %H:%M UTC')"
echo "========================================"

# 1. Poll for any last-minute emails
echo ""
echo "[1/3] Polling inbox..."
python poll_inbox.py

# 2. Generate digest from yesterday's articles
YESTERDAY=$(date -u -d "yesterday" '+%Y-%m-%d' 2>/dev/null || date -u -v-1d '+%Y-%m-%d')
echo ""
echo "[2/3] Generating digest for $YESTERDAY..."
python generate_digest.py "$YESTERDAY"

# 3. Clean up old episodes from storage
echo ""
echo "[3/3] Cleaning up old episodes..."
python -c "
from config_loader import load_config
from storage import delete_old_episodes
config = load_config()
if config.get('storage', {}).get('bucket'):
    delete_old_episodes(config, keep_days=30)
else:
    print('  Storage not configured, skipping cleanup')
"

echo ""
echo "Done."
