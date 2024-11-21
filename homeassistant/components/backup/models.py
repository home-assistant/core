"""Models for the backup integration."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True, kw_only=True)
class AddonInfo:
    """Addon information."""

    name: str
    slug: str
    version: str


@dataclass(frozen=True, kw_only=True)
class AgentBackup:
    """Base backup class."""

    addons: list[AddonInfo]
    backup_id: str
    date: str
    database_included: bool
    folders: list[str]
    homeassistant_included: bool
    homeassistant_version: str | None  # None if homeassistant_included is False
    name: str
    protected: bool
    size: int

    def as_dict(self) -> dict:
        """Return a dict representation of this backup."""
        return asdict(self)
