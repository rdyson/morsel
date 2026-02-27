---
name: morsel
description: Queue article URLs for the Morsel daily podcast digest
requires:
  env:
    - MORSEL_INBOX
---

# Morsel — URL to Podcast Queue

When the user shares a URL, send it to their Morsel inbox for inclusion in the next daily podcast digest.

## Behavior

- When the user pastes or shares one or more URLs, send each URL as a separate email to the Morsel inbox using the AgentMail skill.
- The email subject should be "Morsel: <url>"
- The email body should contain only the URL, nothing else.
- Send to: $MORSEL_INBOX
- After sending, confirm briefly like "Queued for Morsel" — keep it short.
- If the user's message contains a URL alongside other conversation, use judgment — only queue URLs that the user clearly wants to save for later reading. If they're asking a question about a URL or discussing it, don't queue it.
- If the user explicitly says something like "add to morsel" or "queue this", always queue it.
