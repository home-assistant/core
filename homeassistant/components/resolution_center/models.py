"""Models for Resolution Center."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.backports.enum import StrEnum


class IssueSeverity(StrEnum):
    """Issue severity."""

    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class Issue:
    """Issue data type."""

    breaks_in_ha_version: str | None
    domain: str
    issue_id: str
    dismissed: bool
    dismissed_version_major: int | None
    dismissed_version_minor: int | None
    dismissed_version_patch: int | None
    is_fixable: bool
    learn_more_url: str | None
    severity: IssueSeverity
    translation_key: str | None
    translation_placeholders: dict[str, str] | None
