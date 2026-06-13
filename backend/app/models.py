"""Data models shared across the app."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Priority(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Category(str, Enum):
    PAYMENT_ISSUE = "PAYMENT_ISSUE"
    SERVER_DOWN = "SERVER_DOWN"
    CLIENT_COMPLAINT = "CLIENT_COMPLAINT"
    URGENT_REQUEST = "URGENT_REQUEST"
    SECURITY_ALERT = "SECURITY_ALERT"
    SUBSCRIPTION = "SUBSCRIPTION"
    SPAM = "SPAM"
    GENERAL = "GENERAL"


class Email(BaseModel):
    """Represents an incoming email, regardless of where it came from."""

    id: str
    from_: str = Field(alias="from")
    subject: str
    body: str
    received_at: datetime

    model_config = {"populate_by_name": True}


class Classification(BaseModel):
    """Holds the classification result for an email."""

    important: bool
    priority: Priority
    category: Category
    reason: str
    classified_by: str = "rules"


class Notification(BaseModel):
    """A classified email that gets saved and shown on the dashboard."""

    id: str
    from_: str = Field(alias="from")
    subject: str
    priority: Priority
    category: Category
    reason: str
    received_at: datetime
    classified_by: str

    model_config = {"populate_by_name": True}
