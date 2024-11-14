"""Models for the backup integration."""

from dataclasses import asdict, dataclass


@dataclass()
class BaseBackup:
    """Base backup class."""

    date: str
    name: str
    protected: bool
    slug: str
    size: float

    def as_dict(self) -> dict:
        """Return a dict representation of this backup."""
        return asdict(self)


@dataclass()
class BackupUploadMetadata:
    """Backup upload metadata."""

    date: str  # The date the backup was created
    slug: str  # The slug of the backup
    size: float  # The size of the backup (in bytes)
    name: str  # The name of the backup
    homeassistant: str  # The version of Home Assistant that created the backup
    protected: bool  # If the backup is protected
