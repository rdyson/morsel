# Morsel
<img src="logo.png" alt="Morsel" width="200">


Daily article digest in a podcast. Forward links throughout the day, get a single podcast episode each morning summarizing everything.

## How it works

1. Forward article links to an email address
2. A poller picks up new emails, extracts URLs, and scrapes the articles
3. A daily cron job generates a podcast script (Claude API), converts it to audio (Edge TTS), and uploads the episode to S3-compatible storage
4. Subscribe to the RSS feed in any podcast app

## Requirements

- A machine that stays on for daily automation (VM, VPS, Raspberry Pi, etc.) — or run manually on any machine including macOS
- Python 3.10+
- [AgentMail](https://agentmail.to) account (email ingestion; free up to 3,000 emails/month)
- [Anthropic API key](https://console.anthropic.com) (summarization, about $0.10 for 8 medium-length articles; YMMV and you can try different Anthropic models)
- S3-compatible storage with public access - [Cloudflare R2](https://developers.cloudflare.com/r2/) (10GB free), [AWS S3](https://aws.amazon.com/s3/), [Backblaze B2](https://www.backblaze.com/b2/), etc.
- Edge TTS is free and requires no API key or setup.

## Setup

```bash
git clone https://github.com/rdyson/morsel.git
cd morsel
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
```

Copy the example config and fill in your credentials.

### AgentMail inbox

Create an inbox at [AgentMail](https://agentmail.to) and put your API key and inbox email address in `config.json`. You can use an obscure email address to reduce the chances of getting spam.

Add your email address(es) to `allowed_senders` to restrict who can submit links. If the list is empty, all senders are accepted.

### S3-compatible storage

Any S3-compatible provider works. Example with Cloudflare R2:

1. Create a bucket in the [Cloudflare dashboard](https://dash.cloudflare.com) → R2
2. Enable public access on the bucket (gives you a `pub-xxx.r2.dev` URL)
3. Create an API token with read/write access
4. Fill in the `storage` fields in `config.json`

For AWS S3, set `endpoint_url` to `https://s3.<region>.amazonaws.com`. For Backblaze B2, use their S3-compatible endpoint.


### Optional customization

A `cover.png` is included in the repo. Upload it to your storage bucket and set `podcast.image_url` in `config.json` to its public URL. Or use your own square image (minimum 1400x1400px).

Set your preferred voice in `config.json` under `tts.voice`.

```json
{
  "agentmail": {
    "api_key": "YOUR_AGENTMAIL_API_KEY",
    "email_address": "foo@agentmail.to",
    "allowed_senders": ["you@example.com"]
  },
  "anthropic": {
    "api_key": "sk-ant-...",
    "model": "claude-haiku-3-5-20241022"
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
    "description": "Daily article digest in summarized audio",
    "author": "Morsel",
    "image_url": ""
  },
  "tts": {
    "voice": "en-US-AndrewMultilingualNeural"
  }
}
```

## Usage

### 1. Set up the daily cron job

```bash
crontab -e
```

```
0 7 * * * /path/to/morsel/run_daily.sh >> /path/to/morsel/data/cron.log 2>&1
```

This runs daily at 7am UTC. Customize your cron job with help from [Crontab Guru](https://crontab.guru). It polls for new emails, generates yesterday's digest, uploads to storage, and cleans up episodes older than 30 days.

### 2. Subscribe to the feed

Add your feed URL to any podcast app (Apple Podcasts, Overcast, Pocket Casts, etc.):

```
https://<your-public-url>/feed.xml
```

### 3. Forward links

Send or forward article URLs to your AgentMail email address from anywhere — Slack, WhatsApp, email, etc. They'll be included in the next morning's episode.

### Running manually

You can also run each step individually:

```bash
# Poll for new emails and queue articles
python poll_inbox.py

# Poll continuously (every 60s)
python poll_inbox.py --watch

# Generate a digest for a specific date
python generate_digest.py 2026-02-20
```

## License

MIT
