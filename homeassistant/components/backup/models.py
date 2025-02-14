"""Models for the backup integration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Self

from homeassistant.exceptions import HomeAssistantError


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
class BaseBackup:
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


@dataclass(frozen=True, kw_only=True)
class AgentBackup(BaseBackup):
    """Agent backup class."""

    protected: bool
    size: int

    def as_dict(self) -> dict:
        """Return a dict representation of this backup."""
        return asdict(self)

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


class BackupError(HomeAssistantError):
    """Base class for backup errors."""

    error_code = "unknown"


class BackupAgentError(BackupError):
    """Base class for backup agent errors."""

    error_code = "backup_agent_error"


class BackupManagerError(BackupError):
    """Backup manager error."""

    error_code = "backup_manager_error"


class BackupReaderWriterError(BackupError):
    """Backup reader/writer error."""

    error_code = "backup_reader_writer_error"


class BackupNotFound(BackupAgentError, BackupManagerError):
    """Raised when a backup is not found."""

    error_code = "backup_not_found"
