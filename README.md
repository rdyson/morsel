# Morsel

Daily article digest in bite-sized audio. Forward links throughout the day, get a single podcast episode each morning summarizing everything.

## How it works

1. You forward article links to an email address
2. A poller picks up new emails, extracts URLs, and scrapes the articles
3. A daily cron job generates a podcast script (Claude API), converts it to audio (Edge TTS), and uploads the episode to S3-compatible storage
4. You subscribe to the RSS feed in any podcast app

## Requirements

- A machine that stays on (VM, VPS, Raspberry Pi, etc.)
- Python 3.10+
- [AgentMail](https://agentmail.to) account (email ingestion; free up to 3,000 emails/month)
- [Anthropic API key](https://console.anthropic.com) (summarization)
- S3-compatible storage with public access - [Cloudflare R2](https://developers.cloudflare.com/r2/) (10GB free), [AWS S3](https://aws.amazon.com/s3/), [Backblaze B2](https://www.backblaze.com/b2/), etc.

Edge TTS is free and requires no API key.

## Setup

```bash
git clone https://github.com/rdyson/morsel.git
cd morsel
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Copy the example config and fill in your credentials:

```bash
cp config.example.json config.json
```

```json
{
  "agentmail": {
    "api_key": "YOUR_AGENTMAIL_API_KEY",
    "email_address": "foo@agentmail.to"
  },
  "anthropic": {
    "api_key": "sk-ant-..."
  },
  "storage": {
    "endpoint_url": "https://<account-id>.r2.cloudflarestorage.com (Cloudflare R2) or https://s3.<region>.amazonaws.com (AWS S3) or https://s3.<region>.backblazeb2.com (Backblaze B2)",
    "access_key_id": "YOUR_ACCESS_KEY_ID",
    "secret_access_key": "YOUR_SECRET_ACCESS_KEY",
    "bucket": "YOUR_BUCKET_NAME",
    "public_url": "https://your-public-bucket-url"
  },
  "podcast": {
    "title": "Morsel",
    "description": "Daily article digest in bite-sized audio",
    "author": "Morsel"
  },
  "tts": {
    "voice": "en-US-AndrewMultilingualNeural"
  },
  "data_dir": "data"
}
```

### AgentMail inbox

Create an inbox at [AgentMail](https://agentmail.to) and put the email address in `config.json`.

### S3-compatible storage

Any S3-compatible provider works. Example with Cloudflare R2:

1. Create a bucket in the [Cloudflare dashboard](https://dash.cloudflare.com) → R2
2. Enable public access on the bucket (gives you a `pub-xxx.r2.dev` URL)
3. Create an API token with read/write access
4. Fill in the `storage` fields in `config.json`

For AWS S3, set `endpoint_url` to `https://s3.<region>.amazonaws.com`. For Backblaze B2, use their S3-compatible endpoint.

## Usage

### Forward links

Send or forward article URLs to your AgentMail email address from anywhere — Slack, WhatsApp, email, etc.

### Poll for new articles

```bash
python poll_inbox.py
```

This checks for new emails, scrapes the articles, and queues them in `data/queue/{date}/`.

To poll continuously:

```bash
python poll_inbox.py --watch
```

### Generate a digest

```bash
python generate_digest.py 2026-02-20
```

Generates the podcast episode from that day's queued articles, uploads the MP3 and RSS feed to storage.

### Automate with cron

Run the daily digest at 7am UTC:

```bash
crontab -e
```

```
0 7 * * * /path/to/morsel/run_daily.sh >> /path/to/morsel/data/cron.log 2>&1
```

`run_daily.sh` does a final poll, generates yesterday's digest, uploads to storage, and cleans up episodes older than 7 days.

### Subscribe

Add your feed URL to any podcast app:

```
https://<your-public-url>/feed.xml
```

## Voices

Edge TTS offers many voices. List English options:

```bash
edge-tts --list-voices | grep en-
```

Set your preferred voice in `config.json` under `tts.voice`.

## License

MIT
