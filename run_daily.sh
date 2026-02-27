#!/bin/bash
#
# Daily podcast digest generation.
#
# 1. Polls AgentMail for any remaining unprocessed emails
# 2. Generates the digest from the queue
# 3. Uploads audio + feed to storage
# 4. Cleans up old episodes from storage
#
# Crontab entry (4am UTC):
#   0 4 * * * /path/to/morsel/run_daily.sh >> /path/to/morsel/data/cron.log 2>&1

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

# 2. Generate digest from queued articles
echo ""
echo "[2/3] Generating digest..."
python generate_digest.py

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
