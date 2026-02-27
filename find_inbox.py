#!/usr/bin/env python3
"""
List your AgentMail inboxes to find the inbox_id for config.json.

Usage:
    AGENTMAIL_API_KEY=your-key python find_inbox.py
"""

import os
import sys
from agentmail import AgentMail
from config_loader import load_config


def main():
    config = load_config()
    client = AgentMail(api_key=config["agentmail"]["api_key"])

    response = client.inboxes.list()
    if not response.inboxes:
        print("No inboxes found. Create one first in the AgentMail console.")
        sys.exit(1)

    print(f"Found {response.count} inbox(es):\n")
    for inbox in response.inboxes:
        print(f"  Inbox ID:     {inbox.inbox_id}")
        print(f"  Display name: {inbox.display_name or '(none)'}")
        print(f"  Created:      {inbox.created_at}")
        print()

    if response.count == 1:
        inbox_id = response.inboxes[0].inbox_id
        print(f"→ Put this in config.json as agentmail.inbox_id: \"{inbox_id}\"")


if __name__ == "__main__":
    main()
