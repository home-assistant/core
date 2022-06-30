"""Models for Resolution Center."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from homeassistant.core import HomeAssistant


@dataclass(frozen=True)
class Issue:
    """Issue data type."""

    breaks_in_ha_version: str | None
    description_i18n_key: str | None
    domain: str
    issue_id: str
    dismissed: bool
    dismissed_version_major: int | None
    dismissed_version_minor: int | None
    dismissed_version_patch: int | None
    is_fixable: bool
    fix_label_i18n_key: str | None
    learn_more_url: str | None
    placeholders_i18n_keys: dict[str, str] | None
    severity: str
    title_i18n_key: str


class ResolutionCenterProtocol(Protocol):
    """Define the format of resolution center platforms."""

    async def async_fix_issue(self, hass: HomeAssistant, issue_id: str) -> bool:
        """Fix a fixable issue."""
