"""Models for the backup integration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Self


@dataclass(frozen=True, kw_only=True)
class AddonInfo:
    """Addon information."""

    name: str
    slug: str
    version: str


class Folder(StrEnum):
    """Folder type."""

    SHARE = "share"
    ADDONS = "addons/local"
    SSL = "ssl"
    MEDIA = "media"


@dataclass(frozen=True, kw_only=True)
class AgentBackup:
    """Base backup class."""

    addons: list[AddonInfo]
    backup_id: str
    date: str
    database_included: bool
    extra_metadata: dict[str, bool | str]
    folders: list[Folder]
    homeassistant_included: bool
    homeassistant_version: str | None  # None if homeassistant_included is False
    name: str
    protected: bool
    size: int

    def as_dict(self) -> dict:
        """Return a dict representation of this backup."""
        return asdict(self)

    def as_frontend_json(self) -> dict:
        """Return a dict representation of this backup for sending to frontend."""
        return {
            key: val for key, val in asdict(self).items() if key != "extra_metadata"
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Create an instance from a JSON serialization."""
        return cls(
            addons=[AddonInfo(**addon) for addon in data["addons"]],
            backup_id=data["backup_id"],
            date=data["date"],
            database_included=data["database_included"],
            extra_metadata=data["extra_metadata"],
            folders=[Folder(folder) for folder in data["folders"]],
            homeassistant_included=data["homeassistant_included"],
            homeassistant_version=data["homeassistant_version"],
            name=data["name"],
            protected=data["protected"],
            size=data["size"],
        )
