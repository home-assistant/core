"""Constants for the Home Assistant Labs integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypedDict

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.storage import Store

DOMAIN = "labs"

STORAGE_KEY = "core.labs"
STORAGE_VERSION = 1

EVENT_LABS_UPDATED = "labs_updated"


class EventLabsUpdatedData(TypedDict):
    """Event data for labs_updated event."""

    domain: str
    preview_feature: str
    enabled: bool


@dataclass(frozen=True, kw_only=True, slots=True)
class LabPreviewFeature:
    """Lab preview feature definition."""

    domain: str
    preview_feature: str
    is_built_in: bool = True
    feedback_url: str | None = None
    learn_more_url: str | None = None
    report_issue_url: str | None = None

    @property
    def full_key(self) -> str:
        """Return the full key for the preview feature (domain.preview_feature)."""
        return f"{self.domain}.{self.preview_feature}"

    def to_dict(self, enabled: bool) -> dict[str, str | bool | None]:
        """Return a serialized version of the preview feature.

        Args:
            enabled: Whether the preview feature is currently enabled

        Returns:
            Dictionary with preview feature data including enabled status
        """
        return {
            "preview_feature": self.preview_feature,
            "domain": self.domain,
            "enabled": enabled,
            "is_built_in": self.is_built_in,
            "feedback_url": self.feedback_url,
            "learn_more_url": self.learn_more_url,
            "report_issue_url": self.report_issue_url,
        }


type LabsStoreData = dict[str, set[tuple[str, str]]]


@dataclass
class LabsData:
    """Storage class for Labs global data."""

    store: Store[LabsStoreData]
    data: LabsStoreData
    preview_features: dict[str, LabPreviewFeature] = field(default_factory=dict)


LABS_DATA: HassKey[LabsData] = HassKey(DOMAIN)
