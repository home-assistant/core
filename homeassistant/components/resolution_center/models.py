"""Models for Resolution Center."""
from __future__ import annotations

from homeassistant.backports.enum import StrEnum


class IssueSeverity(StrEnum):
    """Issue severity."""

    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
