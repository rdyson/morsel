"""
Upload files to S3-compatible storage and manage the podcast RSS feed.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

from config_loader import load_config, get_data_dir


def get_storage_client(config: dict):
    """Create a boto3 S3-compatible client."""
    import boto3

    storage_config = config["storage"]
    session = boto3.session.Session()
    return session.client(
        "s3",
        endpoint_url=storage_config["endpoint_url"],
        aws_access_key_id=storage_config["access_key_id"],
        aws_secret_access_key=storage_config["secret_access_key"],
        region_name="auto",
    )


def upload_file(config: dict, local_path: Path, key: str, content_type: str) -> str:
    """Upload a file. Returns the public URL."""
    client = get_storage_client(config)
    bucket = config["storage"]["bucket"]
    public_url = config["storage"]["public_url"].rstrip("/")

    extra_args = {"ContentType": content_type}
    # Prevent CDN caching for files that change frequently (e.g. feed.xml)
    if content_type == "application/rss+xml":
        extra_args["CacheControl"] = "no-cache, max-age=0"

    client.upload_file(
        str(local_path),
        bucket,
        key,
        ExtraArgs=extra_args,
    )

    url = f"{public_url}/{key}"
    print(f"  Uploaded: {key} → {url}")
    return url


def delete_old_episodes(config: dict, keep_days: int = 30):
    """Delete audio files older than keep_days from storage."""
    client = get_storage_client(config)
    bucket = config["storage"]["bucket"]

    response = client.list_objects_v2(Bucket=bucket, Prefix="audio/")
    if "Contents" not in response:
        return

    now = datetime.now(timezone.utc)
    deleted = 0
    for obj in response["Contents"]:
        age = (now - obj["LastModified"]).days
        if age > keep_days:
            client.delete_object(Bucket=bucket, Key=obj["Key"])
            print(f"  Deleted old episode: {obj['Key']} ({age} days old)")
            deleted += 1

    if deleted:
        print(f"  Cleaned up {deleted} old episode(s)")


def _escape_xml(text: str) -> str:
    """Escape text for XML content."""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def generate_feed(config: dict, episodes: list[dict]) -> str:
    """Generate an RSS podcast feed XML string.

    episodes: list of dicts with keys:
        title, description, audio_url, audio_size, date, show_notes
    """
    podcast_config = config.get("podcast", {})
    title = _escape_xml(podcast_config.get("title", "Morsel"))
    description = _escape_xml(podcast_config.get("description", "Daily article digest in bite-sized audio"))
    author = _escape_xml(podcast_config.get("author", "Morsel"))
    public_url = config["storage"]["public_url"].rstrip("/")
    feed_url = f"{public_url}/feed.xml"

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:atom="http://www.w3.org/2005/Atom">',
        '  <channel>',
        f'    <title>{title}</title>',
        f'    <description>{description}</description>',
        '    <language>en</language>',
        '    <generator>morsel</generator>',
        f'    <itunes:author>{author}</itunes:author>',
        '    <itunes:explicit>false</itunes:explicit>',
    ]

    # Podcast image (optional)
    image_url = podcast_config.get("image_url")
    if image_url:
        url = _escape_xml(image_url)
        lines.append(f'    <itunes:image href="{url}" />')
        lines.append(f'    <image>')
        lines.append(f'      <url>{url}</url>')
        lines.append(f'      <title>{title}</title>')
        lines.append(f'    </image>')

    lines.append(f'    <atom:link href="{_escape_xml(feed_url)}" rel="self" type="application/rss+xml" />')

    # Add episodes (newest first)
    for ep in sorted(episodes, key=lambda e: e["date"], reverse=True):
        pub_date = datetime.fromisoformat(ep["date"]).replace(tzinfo=timezone.utc)
        guid = hashlib.sha256(ep["audio_url"].encode()).hexdigest()[:16]

        lines.append('    <item>')
        lines.append(f'      <title>{_escape_xml(ep["title"])}</title>')
        lines.append(f'      <description><![CDATA[{ep.get("show_notes", "")}]]></description>')
        lines.append(f'      <pubDate>{format_datetime(pub_date)}</pubDate>')
        lines.append(f'      <guid isPermaLink="false">{guid}</guid>')
        lines.append(f'      <enclosure url="{_escape_xml(ep["audio_url"])}" length="{ep.get("audio_size", 0)}" type="audio/mpeg" />')
        lines.append(f'      <itunes:duration>{ep.get("duration", "0")}</itunes:duration>')
        lines.append('    </item>')

    lines.append('  </channel>')
    lines.append('</rss>')

    return '\n'.join(lines)


def upload_episode(config: dict, audio_path: Path, show_notes_path: Path, episode_date: str) -> dict:
    """Upload an episode's audio to storage and return episode metadata."""
    audio_key = f"audio/digest-{episode_date}.mp3"
    audio_url = upload_file(config, audio_path, audio_key, "audio/mpeg")
    audio_size = audio_path.stat().st_size

    show_notes = show_notes_path.read_text() if show_notes_path.exists() else ""

    return {
        "title": f"Morsel — {episode_date}",
        "description": show_notes,
        "show_notes": show_notes,
        "audio_url": audio_url,
        "audio_size": audio_size,
        "date": episode_date,
    }


def load_episode_index(config: dict) -> list[dict]:
    """Load the episode index from local data dir."""
    data_dir = get_data_dir()
    index_path = data_dir / "episodes.json"
    if index_path.exists():
        return json.loads(index_path.read_text())
    return []


def save_episode_index(config: dict, episodes: list[dict]):
    """Save the episode index to local data dir."""
    data_dir = get_data_dir()
    index_path = data_dir / "episodes.json"
    index_path.write_text(json.dumps(episodes, indent=2))


def update_feed(config: dict, new_episode: dict):
    """Add a new episode to the index, regenerate the feed, and upload to storage."""
    # Load existing episodes
    episodes = load_episode_index(config)

    # Check for duplicate
    if any(ep["date"] == new_episode["date"] for ep in episodes):
        # Replace existing episode for that date
        episodes = [ep for ep in episodes if ep["date"] != new_episode["date"]]

    episodes.append(new_episode)

    # Only keep episodes from the last 30 days in the feed
    save_episode_index(config, episodes)

    # Generate and upload feed
    feed_xml = generate_feed(config, episodes)
    data_dir = get_data_dir()
    feed_path = data_dir / "feed.xml"
    feed_path.write_text(feed_xml)

    upload_file(config, feed_path, "feed.xml", "application/rss+xml")

    public_url = config["storage"]["public_url"].rstrip("/")
    print(f"\n  Feed URL: {public_url}/feed.xml")
