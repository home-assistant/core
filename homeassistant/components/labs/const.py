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

    feature_id: str
    enabled: bool


@dataclass(frozen=True, kw_only=True, slots=True)
class LabFeature:
    """Lab feature definition."""

    domain: str
    feature: str
    feedback_url: str | None = None
    learn_more_url: str | None = None
    report_issue_url: str | None = None

    @property
    def full_key(self) -> str:
        """Return the full key for the feature (domain.feature)."""
        return f"{self.domain}.{self.feature}"


type LabsStoreData = dict[str, dict[str, bool]]


@dataclass
class LabsData:
    """Storage class for Labs global data."""

    store: Store[LabsStoreData]
    data: LabsStoreData
    features: dict[str, LabFeature] = field(default_factory=dict)


LABS_DATA: HassKey[LabsData] = HassKey(DOMAIN)
