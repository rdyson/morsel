"""
Upload files to Cloudflare R2 and manage the podcast RSS feed.
"""

import hashlib
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

import httpx

from config_loader import load_config, get_data_dir


def get_r2_client(config: dict):
    """Create an httpx-based S3-compatible client for R2."""
    # We use boto3 for S3-compat operations
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


def upload_file(config: dict, local_path: Path, r2_key: str, content_type: str) -> str:
    """Upload a file to R2. Returns the public URL."""
    client = get_r2_client(config)
    bucket = config["storage"]["bucket"]
    public_url = config["storage"]["public_url"].rstrip("/")

    client.upload_file(
        str(local_path),
        bucket,
        r2_key,
        ExtraArgs={"ContentType": content_type},
    )

    url = f"{public_url}/{r2_key}"
    print(f"  Uploaded: {r2_key} → {url}")
    return url


def delete_old_episodes(config: dict, keep_days: int = 7):
    """Delete audio files older than keep_days from R2."""
    client = get_r2_client(config)
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


def generate_feed(config: dict, episodes: list[dict]) -> str:
    """Generate an RSS podcast feed XML string.

    episodes: list of dicts with keys:
        title, description, audio_url, audio_size, date, show_notes
    """
    podcast_config = config.get("podcast", {})
    title = podcast_config.get("title", "Morsel")
    description = podcast_config.get("description", "Daily article digest in bite-sized audio")
    author = podcast_config.get("author", "Morsel")
    public_url = config["storage"]["public_url"].rstrip("/")
    feed_url = f"{public_url}/feed.xml"

    # Build RSS XML
    rss = ET.Element("rss", {
        "version": "2.0",
        "xmlns:itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
        "xmlns:atom": "http://www.w3.org/2005/Atom",
    })

    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = title
    ET.SubElement(channel, "description").text = description
    ET.SubElement(channel, "language").text = "en"
    ET.SubElement(channel, "generator").text = "morsel"
    ET.SubElement(channel, "{http://www.itunes.com/dtds/podcast-1.0.dtd}author").text = author
    ET.SubElement(channel, "{http://www.itunes.com/dtds/podcast-1.0.dtd}explicit").text = "false"

    # Self-referencing atom link (helps podcast apps)
    ET.SubElement(channel, "{http://www.w3.org/2005/Atom}link", {
        "href": feed_url,
        "rel": "self",
        "type": "application/rss+xml",
    })

    # Add episodes (newest first)
    for ep in sorted(episodes, key=lambda e: e["date"], reverse=True):
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = ep["title"]
        ET.SubElement(item, "description").text = ep.get("show_notes", "")

        pub_date = datetime.fromisoformat(ep["date"]).replace(tzinfo=timezone.utc)
        ET.SubElement(item, "pubDate").text = format_datetime(pub_date)

        # Unique ID per episode
        guid = hashlib.sha256(ep["audio_url"].encode()).hexdigest()[:16]
        ET.SubElement(item, "guid", {"isPermaLink": "false"}).text = guid

        ET.SubElement(item, "enclosure", {
            "url": ep["audio_url"],
            "length": str(ep.get("audio_size", 0)),
            "type": "audio/mpeg",
        })

        ET.SubElement(item, "{http://www.itunes.com/dtds/podcast-1.0.dtd}duration").text = ep.get("duration", "0")

    ET.indent(rss, space="  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(rss, encoding="unicode")


def upload_episode(config: dict, audio_path: Path, show_notes_path: Path, episode_date: str) -> dict:
    """Upload an episode's audio to R2 and return episode metadata."""
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
    data_dir = get_data_dir(config)
    index_path = data_dir / "episodes.json"
    if index_path.exists():
        return json.loads(index_path.read_text())
    return []


def save_episode_index(config: dict, episodes: list[dict]):
    """Save the episode index to local data dir."""
    data_dir = get_data_dir(config)
    index_path = data_dir / "episodes.json"
    index_path.write_text(json.dumps(episodes, indent=2))


def update_feed(config: dict, new_episode: dict):
    """Add a new episode to the index, regenerate the feed, and upload to R2."""
    # Load existing episodes
    episodes = load_episode_index(config)

    # Check for duplicate
    if any(ep["date"] == new_episode["date"] for ep in episodes):
        # Replace existing episode for that date
        episodes = [ep for ep in episodes if ep["date"] != new_episode["date"]]

    episodes.append(new_episode)

    # Only keep episodes from the last 7 days in the feed
    save_episode_index(config, episodes)

    # Generate and upload feed
    feed_xml = generate_feed(config, episodes)
    data_dir = get_data_dir(config)
    feed_path = data_dir / "feed.xml"
    feed_path.write_text(feed_xml)

    upload_file(config, feed_path, "feed.xml", "application/rss+xml")

    public_url = config["storage"]["public_url"].rstrip("/")
    print(f"\n  Feed URL: {public_url}/feed.xml")
