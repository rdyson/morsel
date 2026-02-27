"""
Scrape articles using Jina Reader API (free, no key needed).
Returns clean markdown from any URL.
"""

import httpx
import re
import time

JINA_PREFIX = "https://r.jina.ai/"
TIMEOUT = 60
MAX_RETRIES = 3
RETRY_DELAY = 5


def scrape_url(url: str) -> dict:
    """Scrape a single URL via Jina Reader. Returns dict with title, url, content."""
    jina_url = f"{JINA_PREFIX}{url}"
    headers = {
        "Accept": "text/markdown",
        "X-No-Cache": "true",
    }

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = httpx.get(jina_url, headers=headers, timeout=TIMEOUT, follow_redirects=True)
            resp.raise_for_status()
            break
        except (httpx.TimeoutException, httpx.HTTPStatusError) as e:
            last_error = e
            if attempt < MAX_RETRIES:
                print(f"    Attempt {attempt}/{MAX_RETRIES} failed ({e}), retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
            else:
                raise last_error

    text = resp.text

    # Jina returns markdown with a title line at the top like "Title: ..."
    title = ""
    title_match = re.match(r"^Title:\s*(.+)$", text, re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()

    return {
        "title": title or url,
        "url": url,
        "content": text,
    }
