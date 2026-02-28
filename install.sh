#!/usr/bin/env bash
#
# Morsel installer — install from the latest GitHub release.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/rdyson/morsel/master/install.sh | bash
#
# Environment variables:
#   MORSEL_DIR  — install directory (default: ./morsel)
#

set -euo pipefail

REPO="rdyson/morsel"
INSTALL_DIR="${MORSEL_DIR:-./morsel}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

info()  { printf '\033[1;34m==>\033[0m %s\n' "$1"; }
warn()  { printf '\033[1;33mWarning:\033[0m %s\n' "$1"; }
err()   { printf '\033[1;31mError:\033[0m %s\n' "$1" >&2; exit 1; }

prompt_value() {
  local label="$1" default="${2:-}"
  if [ -n "$default" ]; then
    printf '%s [%s]: ' "$label" "$default" > /dev/tty
  else
    printf '%s: ' "$label" > /dev/tty
  fi
  local value
  read -r value < /dev/tty
  printf '%s' "${value:-$default}"
}

prompt_secret() {
  local label="$1"
  printf '%s: ' "$label" > /dev/tty
  local value
  read -rs value < /dev/tty
  printf '\n' > /dev/tty
  printf '%s' "$value"
}

prompt_yn() {
  local label="$1" default="${2:-y}"
  if [ "$default" = "y" ]; then
    printf '%s [Y/n]: ' "$label" > /dev/tty
  else
    printf '%s [y/N]: ' "$label" > /dev/tty
  fi
  local value
  read -r value < /dev/tty
  value="${value:-$default}"
  case "$value" in
    [Yy]*) return 0 ;;
    *)     return 1 ;;
  esac
}

# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------

info "Checking prerequisites..."

command -v curl  >/dev/null 2>&1 || err "curl is required but not found. Install it and try again."
command -v tar   >/dev/null 2>&1 || err "tar is required but not found. Install it and try again."
command -v python3 >/dev/null 2>&1 || err "python3 is required but not found. Install Python 3.8+ and try again."

python_version="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
python_major="${python_version%%.*}"
python_minor="${python_version##*.}"
if [ "$python_major" -lt 3 ] || { [ "$python_major" -eq 3 ] && [ "$python_minor" -lt 8 ]; }; then
  err "Python 3.8+ is required (found $python_version). Please upgrade and try again."
fi

info "Prerequisites OK (python $python_version)"

# ---------------------------------------------------------------------------
# Resolve latest release
# ---------------------------------------------------------------------------

info "Fetching latest release..."

api_url="https://api.github.com/repos/${REPO}/releases/latest"
release_json="$(curl -fsSL "$api_url" 2>/dev/null)" \
  || err "Could not reach GitHub API. Check your internet connection or ensure a release exists at https://github.com/${REPO}/releases"

tarball_url="$(printf '%s' "$release_json" | python3 -c "import sys,json; print(json.load(sys.stdin)['tarball_url'])" 2>/dev/null)" \
  || err "No releases found. Create one first: gh release create v0.1.0 --generate-notes"

tag="$(printf '%s' "$release_json" | python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'])" 2>/dev/null)"

info "Latest release: $tag"

# ---------------------------------------------------------------------------
# Download & extract
# ---------------------------------------------------------------------------

info "Installing to $INSTALL_DIR..."

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

curl -fsSL "$tarball_url" -o "$tmpdir/morsel.tar.gz"
tar -xzf "$tmpdir/morsel.tar.gz" -C "$tmpdir"

# GitHub tarballs extract into a directory like rdyson-morsel-<sha>/
extracted="$(find "$tmpdir" -mindepth 1 -maxdepth 1 -type d | head -1)"

mkdir -p "$INSTALL_DIR"
# Copy files, preserving existing config.json
cp -rn "$extracted"/* "$INSTALL_DIR/" 2>/dev/null || cp -r "$extracted"/* "$INSTALL_DIR/"

# ---------------------------------------------------------------------------
# Python environment
# ---------------------------------------------------------------------------

info "Setting up Python environment..."

cd "$INSTALL_DIR"

python3 -m venv venv
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

info "Dependencies installed"

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

if [ -f config.json ]; then
  info "config.json already exists — skipping configuration"
else
  info "Setting up config.json..."
  printf '\n' > /dev/tty
  printf 'Enter your credentials below. Press Enter to accept defaults shown in [brackets].\n' > /dev/tty
  printf 'Secret values are hidden as you type.\n\n' > /dev/tty

  printf 'Need an AgentMail account? Sign up at https://agentmail.to\n\n' > /dev/tty

  agentmail_key="$(prompt_secret "AgentMail API key")"
  [ -z "$agentmail_key" ] && err "AgentMail API key is required."

  agentmail_email="$(prompt_value "AgentMail inbox email (e.g. yourname@agentmail.to)")"
  [ -z "$agentmail_email" ] && err "AgentMail inbox email is required."

  allowed_sender="$(prompt_value "Allowed sender email (optional, press Enter to skip)")"
  if [ -n "$allowed_sender" ]; then
    allowed_senders_json="[\"$allowed_sender\"]"
  else
    allowed_senders_json="[]"
  fi

  printf '\nNeed an Anthropic API key? Get one at https://console.anthropic.com\n\n' > /dev/tty

  anthropic_key="$(prompt_secret "Anthropic API key")"
  [ -z "$anthropic_key" ] && err "Anthropic API key is required."

  printf '\nStorage — S3-compatible provider\n' > /dev/tty
  printf '  Cloudflare R2 (recommended, 10GB free): https://dash.cloudflare.com → R2\n' > /dev/tty
  printf '  AWS S3:                                 https://aws.amazon.com/s3/\n' > /dev/tty
  printf '  Backblaze B2:                           https://www.backblaze.com/b2/\n' > /dev/tty
  printf '\nEndpoint examples:\n' > /dev/tty
  printf '  Cloudflare R2:  https://<account-id>.r2.cloudflarestorage.com\n' > /dev/tty
  printf '  AWS S3:         https://s3.<region>.amazonaws.com\n' > /dev/tty
  printf '  Backblaze B2:   https://s3.<region>.backblazeb2.com\n\n' > /dev/tty

  storage_endpoint="$(prompt_value "Storage endpoint URL")"
  [ -z "$storage_endpoint" ] && err "Storage endpoint URL is required."

  storage_key_id="$(prompt_value "Storage access key ID")"
  [ -z "$storage_key_id" ] && err "Storage access key ID is required."

  storage_secret="$(prompt_secret "Storage secret access key")"
  [ -z "$storage_secret" ] && err "Storage secret access key is required."

  storage_bucket="$(prompt_value "Storage bucket name")"
  [ -z "$storage_bucket" ] && err "Storage bucket name is required."

  storage_public_url="$(prompt_value "Storage public URL (e.g. https://pub-xxx.r2.dev)")"
  [ -z "$storage_public_url" ] && err "Storage public URL is required."

  # Write config.json using python to ensure valid JSON
  python3 -c "
import json, sys
config = {
    'agentmail': {
        'api_key': sys.argv[1],
        'email_address': sys.argv[2],
        'allowed_senders': json.loads(sys.argv[3])
    },
    'anthropic': {
        'api_key': sys.argv[4],
        'model': 'claude-haiku-4-5-20251001'
    },
    'storage': {
        'endpoint_url': sys.argv[5],
        'access_key_id': sys.argv[6],
        'secret_access_key': sys.argv[7],
        'bucket': sys.argv[8],
        'public_url': sys.argv[9]
    },
    'podcast': {
        'title': 'Morsel',
        'description': 'Daily article digest in summarized audio',
        'author': 'Morsel',
        'image_url': ''
    },
    'tts': {
        'voice': 'en-US-AndrewMultilingualNeural'
    }
}
with open('config.json', 'w') as f:
    json.dump(config, f, indent=2)
    f.write('\n')
" "$agentmail_key" "$agentmail_email" "$allowed_senders_json" "$anthropic_key" \
  "$storage_endpoint" "$storage_key_id" "$storage_secret" "$storage_bucket" "$storage_public_url"

  info "config.json created"
fi

# ---------------------------------------------------------------------------
# Data directory
# ---------------------------------------------------------------------------

mkdir -p data

# ---------------------------------------------------------------------------
# Cron job
# ---------------------------------------------------------------------------

abs_dir="$(pwd)"
cron_line="0 4 * * * ${abs_dir}/run_daily.sh >> ${abs_dir}/data/cron.log 2>&1"

printf '\n' > /dev/tty
if prompt_yn "Set up daily cron job?"; then
  cron_hour="$(prompt_value "Hour (UTC, 0-23)" "4")"
  cron_minute="$(prompt_value "Minute (0-59)" "0")"
  cron_line="${cron_minute} ${cron_hour} * * * ${abs_dir}/run_daily.sh >> ${abs_dir}/data/cron.log 2>&1"

  # Append to crontab without duplicating
  existing_cron="$(crontab -l 2>/dev/null || true)"
  if printf '%s' "$existing_cron" | grep -qF "run_daily.sh"; then
    warn "A Morsel cron entry already exists — skipping"
  else
    printf '%s\n%s\n' "$existing_cron" "$cron_line" | crontab -
    info "Cron job installed: $cron_line"
  fi

  # macOS requires Full Disk Access for cron
  if [ "$(uname)" = "Darwin" ]; then
    printf '\n' > /dev/tty
    warn "macOS requires Full Disk Access for cron jobs to run."
    printf '  System Settings → Privacy & Security → Full Disk Access → add /usr/sbin/cron\n' > /dev/tty
  fi
else
  printf 'You can set it up later:\n' > /dev/tty
  printf '  crontab -e\n' > /dev/tty
  printf '  %s\n' "$cron_line" > /dev/tty
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------

printf '\n'
info "Morsel $tag installed to $abs_dir"
printf '\n'
printf 'Next steps:\n'
printf '  1. Review your config:  %s/config.json\n' "$abs_dir"
printf '  2. Subscribe to your podcast feed in any podcast app:\n'
printf '     <your storage public URL>/feed.xml\n'
printf '  3. Forward article URLs to your AgentMail inbox\n'
printf '  4. Wait for the cron job to run, or run manually now:\n'
printf '  cd %s && source venv/bin/activate\n' "$abs_dir"
printf '  python poll_inbox.py && python generate_digest.py\n'
printf '\n'
