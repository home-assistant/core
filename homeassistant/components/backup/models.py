"""Models for the backup integration."""

from dataclasses import asdict, dataclass
from typing import TypedDict


@dataclass()
class BaseBackup:
    """Base backup class."""

    date: str
    slug: str
    size: float
    name: str

    def as_dict(self) -> dict:
        """Return a dict representation of this backup."""
        return asdict(self)


class BackupSyncMetadata(TypedDict):
    """Dictionary type for backup sync metadata."""

    date: str  # The date the backup was created
    slug: str  # The slug of the backup
    size: float  # The size of the backup (in bytes)
    name: str  # The name of the backup
    homeassistant: str  # The version of Home Assistant that created the backup
