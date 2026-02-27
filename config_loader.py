"""
Load config from config.json and provide defaults.
"""

import json
import os
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config() -> dict:
    """Load config, with env var overrides."""
    with open(CONFIG_PATH) as f:
        config = json.load(f)

    # Allow env var overrides
    if os.environ.get("AGENTMAIL_API_KEY"):
        config["agentmail"]["api_key"] = os.environ["AGENTMAIL_API_KEY"]
    if os.environ.get("AGENTMAIL_INBOX_ID"):
        config["agentmail"]["inbox_id"] = os.environ["AGENTMAIL_INBOX_ID"]
    if os.environ.get("ANTHROPIC_API_KEY"):
        config["anthropic"]["api_key"] = os.environ["ANTHROPIC_API_KEY"]

    return config


def get_data_dir(config: dict) -> Path:
    """Return the data directory, creating it if needed."""
    data_dir = Path(__file__).parent / config.get("data_dir", "data")
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
