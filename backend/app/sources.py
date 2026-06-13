"""Email source implementations."""
from __future__ import annotations

import email as email_lib
import imaplib
import json
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from email.header import decode_header
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import List

from .models import Email

log = logging.getLogger("sources")


class EmailSource(ABC):
    @abstractmethod
    def fetch(self) -> List[Email]:
        ...


class MockSource(EmailSource):
    """Loads emails from a local JSON file. for testing without real credentials."""

    def __init__(self, path: str | None = None) -> None:
        self.path = Path(
            path or os.getenv("MOCK_DATA_PATH", "/data/mock/emails.json")
        )

    def fetch(self) -> List[Email]:
        if not self.path.exists():
            return []
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return [Email.model_validate(item) for item in raw]


class ImapSource(EmailSource):
    """Connects to any IMAP server. Works with Gmail too — just use an app password."""

    def __init__(self) -> None:
        self.host = os.getenv("IMAP_HOST", "imap.gmail.com")
        self.port = int(os.getenv("IMAP_PORT", "993"))
        self.user = os.getenv("IMAP_USER", "")
        self.password = os.getenv("IMAP_PASSWORD", "")
        self.mailbox = os.getenv("IMAP_MAILBOX", "INBOX")
        self.limit = int(os.getenv("IMAP_FETCH_LIMIT", "25"))

    def fetch(self) -> List[Email]:
        log.info("connecting to IMAP at %s:%s as %s", self.host, self.port, self.user)
        emails: List[Email] = []
        try:
            conn = imaplib.IMAP4_SSL(self.host, self.port)
        except Exception as exc:
            log.error("IMAP connection failed: %s", exc)
            raise
        try:
            conn.login(self.user, self.password)
            log.info("logged in to IMAP as %s", self.user)
            conn.select(self.mailbox)
            _, data = conn.search(None, "ALL")
            ids = data[0].split()[-self.limit:]
            log.info("fetching %d emails from %s (mailbox has %d total)",
                     len(ids), self.mailbox, len(data[0].split()))
            for num in reversed(ids):
                _, msg_data = conn.fetch(num, "(RFC822)")
                if not msg_data or not isinstance(msg_data[0], tuple):
                    continue
                msg = email_lib.message_from_bytes(msg_data[0][1])
                emails.append(self._to_email(msg, num.decode()))
            log.info("got %d emails", len(emails))
        except imaplib.IMAP4.error as exc:
            log.error("IMAP error for %s: %s", self.user, exc)
            raise
        finally:
            try:
                conn.logout()
            except Exception:  # noqa: BLE001
                pass
        return emails

    @staticmethod
    def _decode(value: str | None) -> str:
        if not value:
            return ""
        parts = decode_header(value)
        out = ""
        for text, enc in parts:
            out += text.decode(enc or "utf-8", errors="replace") if isinstance(text, bytes) else text
        return out

    def _to_email(self, msg, fallback_id: str) -> Email:
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = payload.decode(errors="replace")
                        break
        else:
            payload = msg.get_payload(decode=True)
            body = payload.decode(errors="replace") if payload else ""

        try:
            received = parsedate_to_datetime(msg.get("Date"))
            if received.tzinfo is None:
                received = received.replace(tzinfo=timezone.utc)
        except Exception:  
            received = datetime.now(timezone.utc)

        # Message-ID is the best unique key — fall back to IMAP sequence number if it's missing
        msg_id = msg.get("Message-ID") or f"imap-{fallback_id}"

        return Email(
            id=msg_id.strip(),
            **{"from": self._decode(msg.get("From"))},
            subject=self._decode(msg.get("Subject")),
            body=body.strip(),
            received_at=received,
        )


def get_source() -> EmailSource:
    source = os.getenv("EMAIL_SOURCE", "mock").lower()
    log.info("using email source: %s", source)
    if source in ("imap", "gmail"):
        return ImapSource()
    return MockSource()
