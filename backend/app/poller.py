"""Handles one poll cycle — fetches emails, skips duplicates, and saves the important ones."""
from __future__ import annotations

import logging

from . import storage
from .classifier import classify
from .sources import get_source

log = logging.getLogger("poller")


def poll_once() -> dict:
    log.info("starting poll...")
    source = get_source()
    try:
        inbox = source.fetch()
    except Exception as exc:  # noqa: BLE001
        log.error("couldn't fetch emails: %s", exc)
        return {"fetched": 0, "new": 0, "important": 0, "error": str(exc)}

    new_count = 0
    important_count = 0

    for email in inbox:
        if storage.is_processed(email.id):
            log.debug("already processed, skipping: %r", email.subject)
            continue
        new_count += 1

        result = classify(email)
        storage.mark_processed(email.id)

        if result.important:
            storage.save_notification(email, result)
            important_count += 1
            log.info("flagged as important [%s/%s]: %s", result.priority.value,
                     result.category.value, email.subject)
        else:
            log.info("not important [%s]: %s", result.category.value, email.subject)

    log.info("poll done — fetched %d, %d new, %d important, %d already seen",
             len(inbox), new_count, important_count, len(inbox) - new_count)
    return {"fetched": len(inbox), "new": new_count, "important": important_count}
