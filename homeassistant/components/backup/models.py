"""Models for the backup integration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum


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
    folders: list[Folder]
    homeassistant_included: bool
    homeassistant_version: str | None  # None if homeassistant_included is False
    name: str
    protected: bool
    size: int

    def as_dict(self) -> dict:
        """Return a dict representation of this backup."""
        return asdict(self)
