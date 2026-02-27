#!/usr/bin/env python3
"""
Poll AgentMail for new emails, extract URLs, scrape articles, and queue them.

Usage:
    python poll_inbox.py           # poll once
    python poll_inbox.py --watch   # poll every 60 seconds

Articles are saved to data/queue/{YYYY-MM-DD}/ for the daily digest.
Processed emails are labeled "processed" so they aren't re-scraped.
"""

import argparse
import json
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path

from agentmail import AgentMail
from scrape import scrape_url
from config_loader import load_config, get_data_dir


# Regex to find URLs in email text
URL_PATTERN = re.compile(
    r'https?://[^\s<>\'")\]]+',
    re.IGNORECASE,
)

# Domains to ignore (tracking, signatures, etc.)
IGNORE_DOMAINS = {
    "agentmail.to",
    "agentmail.cc",
    "mailto:",
    "unsubscribe",
    "manage-preferences",
    "list-manage.com",
    "mailchimp.com",
    "fonts.googleapis.com",
    "fonts.gstatic.com",
}


def extract_urls(text: str) -> list[str]:
    """Extract meaningful URLs from email text, filtering out noise."""
    if not text:
        return []

    urls = URL_PATTERN.findall(text)

    # Clean up trailing punctuation
    cleaned = []
    for url in urls:
        url = url.rstrip(".,;:!?)>]}")
        # Skip ignored domains
        if any(domain in url.lower() for domain in IGNORE_DOMAINS):
            continue
        # Skip images and assets
        if any(url.lower().endswith(ext) for ext in (".png", ".jpg", ".gif", ".svg", ".css", ".js")):
            continue
        cleaned.append(url)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for url in cleaned:
        if url not in seen:
            seen.add(url)
            unique.append(url)

    return unique


def queue_article(article: dict, queue_dir: Path) -> Path:
    """Save a scraped article to the daily queue directory."""
    queue_dir.mkdir(parents=True, exist_ok=True)

    # Load or create the articles index
    index_path = queue_dir / "articles.json"
    if index_path.exists():
        articles = json.loads(index_path.read_text())
    else:
        articles = []

    # Check for duplicates by URL
    existing_urls = {a["url"] for a in articles}
    if article["url"] in existing_urls:
        print(f"    Skipping duplicate: {article['url']}")
        return queue_dir

    # Save article content
    slug = re.sub(r"[^a-z0-9]+", "-", article["url"].split("//")[-1].lower())[:80].strip("-")
    idx = len(articles)
    filepath = queue_dir / f"{idx:02d}-{slug}.md"
    filepath.write_text(
        f"# {article['title']}\n\n"
        f"Source: {article['url']}\n\n"
        f"---\n\n"
        f"{article['content']}"
    )

    # Update index
    articles.append({
        "title": article["title"],
        "url": article["url"],
        "file": str(filepath),
        "queued_at": datetime.now().isoformat(),
    })
    index_path.write_text(json.dumps(articles, indent=2))

    print(f"    ✓ Queued: {article['title'][:60]}")
    return filepath


def poll_once(config: dict) -> int:
    """Check for new emails, scrape articles, return count of new articles queued."""
    data_dir = get_data_dir(config)
    today = date.today().isoformat()
    queue_dir = data_dir / "queue" / today

    client = AgentMail(api_key=config["agentmail"]["api_key"])
    inbox = config["agentmail"]["email_address"]

    # Fetch messages without "processed" label
    print(f"Checking inbox {inbox} for new messages...")
    response = client.inboxes.messages.list(inbox, limit=10)

    new_count = 0
    for msg_item in response.messages:
        # Skip already-processed messages
        if "processed" in (msg_item.labels or []):
            continue

        print(f"\n  New email: {msg_item.subject or '(no subject)'}")

        # Get full message for text content
        msg = client.inboxes.messages.get(inbox, msg_item.message_id)
        text = msg.text or ""

        # Extract URLs
        urls = extract_urls(text)
        if not urls:
            # Also try HTML if no URLs in plaintext
            urls = extract_urls(msg.html or "")

        if not urls:
            print("    No URLs found, skipping")
            # Label no-URL emails as processed so we don't keep checking them
            client.inboxes.messages.update(
                inbox, msg_item.message_id, add_labels=["processed"],
            )
            continue

        print(f"    Found {len(urls)} URL(s)")
        scraped = 0
        failed = 0
        for url in urls:
            try:
                article = scrape_url(url)
                queue_article(article, queue_dir)
                new_count += 1
                scraped += 1
            except Exception as e:
                print(f"    ✗ Failed to scrape {url}: {e}")
                failed += 1

        # Only label as processed if at least one URL succeeded,
        # or if all URLs failed (to avoid retrying permanently broken links)
        if scraped > 0 or failed == len(urls):
            label = "processed" if scraped > 0 else "failed"
            client.inboxes.messages.update(
                inbox, msg_item.message_id, add_labels=[label],
            )
            print(f"    Labeled as {label} ({scraped} scraped, {failed} failed)")

    if new_count == 0:
        print("No new articles.")
    else:
        print(f"\n{new_count} new article(s) queued to {queue_dir}/")

    return new_count


def main():
    parser = argparse.ArgumentParser(description="Poll AgentMail for article links")
    parser.add_argument("--watch", action="store_true", help="Poll continuously every 60s")
    parser.add_argument("--interval", type=int, default=60, help="Poll interval in seconds (default: 60)")
    args = parser.parse_args()

    config = load_config()

    if args.watch:
        print(f"Watching inbox (polling every {args.interval}s). Ctrl+C to stop.\n")
        try:
            while True:
                try:
                    poll_once(config)
                except Exception as e:
                    print(f"Error during poll: {e}")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nStopped.")
    else:
        poll_once(config)


if __name__ == "__main__":
    main()
