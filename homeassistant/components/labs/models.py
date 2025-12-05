"""Data models for the Home Assistant Labs integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Self, TypedDict

if TYPE_CHECKING:
    from homeassistant.helpers.storage import Store


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

    def to_dict(self, *, enabled: bool) -> dict[str, str | bool | None]:
        """Return a serialized version of the preview feature."""
        return {
            "preview_feature": self.preview_feature,
            "domain": self.domain,
            "enabled": enabled,
            "is_built_in": self.is_built_in,
            "feedback_url": self.feedback_url,
            "learn_more_url": self.learn_more_url,
            "report_issue_url": self.report_issue_url,
        }


@dataclass(kw_only=True)
class LabsStoreData:
    """Storage data for Labs."""

    preview_feature_status: set[tuple[str, str]]

    @classmethod
    def from_store_format(cls, data: NativeLabsStoreData | None) -> Self:
        """Initialize from storage format."""
        if data is None:
            return cls(preview_feature_status=set())
        return cls(
            preview_feature_status={
                (item["domain"], item["preview_feature"])
                for item in data["preview_feature_status"]
            }
        )

    def to_store_format(self) -> NativeLabsStoreData:
        """Convert to storage format."""
        return {
            "preview_feature_status": [
                {"domain": domain, "preview_feature": preview_feature}
                for domain, preview_feature in self.preview_feature_status
            ]
        }


class NativeLabsStoreData(TypedDict):
    """Storage data for Labs."""

    preview_feature_status: list[NativeLabsStoredFeature]


class NativeLabsStoredFeature(TypedDict):
    """A single preview feature entry in storage format."""

    domain: str
    preview_feature: str


@dataclass
class LabsData:
    """Storage class for Labs global data."""

    store: Store[NativeLabsStoreData]
    data: LabsStoreData
    preview_features: dict[str, LabPreviewFeature] = field(default_factory=dict)
