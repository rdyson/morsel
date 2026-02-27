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
    if os.environ.get("AGENTMAIL_EMAIL_ADDRESS"):
        config["agentmail"]["email_address"] = os.environ["AGENTMAIL_EMAIL_ADDRESS"]
    if os.environ.get("ANTHROPIC_API_KEY"):
        config["anthropic"]["api_key"] = os.environ["ANTHROPIC_API_KEY"]

    return config


DATA_DIR = Path(__file__).parent / "data"


def get_data_dir() -> Path:
    """Return the data directory, creating it if needed."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR
