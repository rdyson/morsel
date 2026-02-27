#!/usr/bin/env python3
"""
Generate a daily podcast digest from queued articles.

Usage:
    python generate_digest.py              # process yesterday's queue
    python generate_digest.py 2026-02-20   # process a specific date
"""

import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import anthropic

from config_loader import load_config, get_data_dir
from tts import generate_audio
from storage import upload_episode, update_feed

DIGEST_PROMPT = """\
You are a podcast host producing a daily article digest. Your show is called "Morsel".

Write a podcast script for today's episode based on the articles below. The script should be:

- **Direct and matter-of-fact** — get to the point, no hype, no filler
- **Calm and measured tone** — think NPR or Bloomberg, not a YouTube tech channel
- **Conversational but not enthusiastic** — you're briefing a busy professional, not selling them on anything
- **10-15 minutes when read aloud** (roughly 1500-2200 words)
- **Well-structured**: very brief intro, cover each story, very brief outro
- **Strictly faithful to the source material** — only include information, claims, and data that appear in the articles themselves
- **No editorializing** — do not add your own opinions, speculation, predictions, or commentary beyond what the article states
- **No extrapolation** — if the article doesn't say it, don't say it. Do not fill gaps with general knowledge or assumptions
- **Attribution** — when summarizing a claim or finding, attribute it ("according to the article", "the author argues", "Stripe's team found")
- Start with the most significant story
- Use short, clean transitions between stories — no forced excitement or clever segues
- No markdown formatting, no headers, no bullet points — just flowing prose meant to be spoken
- No sound effect cues or music notes — just the spoken words
- No superlatives like "incredible", "amazing", "groundbreaking", "exciting" — let the facts speak
- Don't say "welcome back" or reference previous episodes
- Open with a brief greeting and today's date — one sentence, then get into it
- Close with a short sign-off — no more than a sentence

Today's date: {date}
Number of articles: {num_articles}

---

{articles}
"""


def generate_digest(queue_date: str, config: dict) -> Path | None:
    """Generate a podcast digest for the given date. Returns path to MP3 or None."""
    data_dir = get_data_dir(config)
    queue_dir = data_dir / "queue" / queue_date
    digest_dir = data_dir / "digest"
    audio_dir = data_dir / "audio"

    # Load articles
    index_path = queue_dir / "articles.json"
    if not index_path.exists():
        print(f"No articles found for {queue_date} (no {index_path})")
        return None

    articles = json.loads(index_path.read_text())
    if not articles:
        print(f"No articles for {queue_date}, skipping.")
        return None

    print(f"Generating digest for {queue_date} ({len(articles)} articles)...")

    # Build article text for the prompt
    article_texts = []
    for i, article in enumerate(articles, 1):
        content = Path(article["file"]).read_text()
        # Truncate very long articles to stay within context limits
        if len(content) > 15000:
            content = content[:15000] + "\n\n[Article truncated for length]"
        article_texts.append(
            f"=== ARTICLE {i} ===\n"
            f"Title: {article['title']}\n"
            f"URL: {article['url']}\n\n"
            f"{content}\n"
        )

    prompt = DIGEST_PROMPT.format(
        date=queue_date,
        num_articles=len(articles),
        articles="\n".join(article_texts),
    )

    # Generate script via Claude
    print("  Generating script...")
    client = anthropic.Anthropic(api_key=config["anthropic"]["api_key"])
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    script = message.content[0].text
    print(f"  ✓ Script: {len(script.split())} words")

    # Save script
    digest_dir.mkdir(parents=True, exist_ok=True)
    script_path = digest_dir / f"digest-{queue_date}.txt"
    script_path.write_text(script)

    # Save show notes
    show_notes = f"Morsel — {queue_date}\n\n"
    show_notes += "Articles covered in this episode:\n\n"
    for i, article in enumerate(articles, 1):
        show_notes += f"{i}. {article['title']}\n   {article['url']}\n\n"
    notes_path = digest_dir / f"show-notes-{queue_date}.txt"
    notes_path.write_text(show_notes)

    # Generate audio
    print("  Generating audio...")
    voice = config.get("tts", {}).get("voice", "en-US-AndrewMultilingualNeural")
    audio_path = audio_dir / f"digest-{queue_date}.mp3"
    generate_audio(script, audio_path, voice)

    # Upload to R2 and update feed
    if config.get("storage", {}).get("bucket"):
        print("  Uploading to R2...")
        episode = upload_episode(config, audio_path, notes_path, queue_date)
        update_feed(config, episode)
    else:
        print("  (R2 not configured, skipping upload)")

    print(f"\n  Done!")
    print(f"  Script:     {script_path}")
    print(f"  Show notes: {notes_path}")
    print(f"  Audio:      {audio_path}")

    return audio_path


def main():
    config = load_config()

    if len(sys.argv) > 1:
        queue_date = sys.argv[1]
    else:
        # Default to yesterday
        queue_date = (date.today() - timedelta(days=1)).isoformat()

    result = generate_digest(queue_date, config)
    if not result:
        print("No digest generated.")
        sys.exit(1)


if __name__ == "__main__":
    main()
