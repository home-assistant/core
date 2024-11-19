"""Models for the backup integration."""

from dataclasses import asdict, dataclass


@dataclass()
class BaseBackup:
    """Base backup class."""

    backup_id: str
    date: str
    name: str
    protected: bool
    size: float

    def as_dict(self) -> dict:
        """Return a dict representation of this backup."""
        return asdict(self)


@dataclass()
class BackupUploadMetadata:
    """Backup upload metadata."""

    backup_id: str  # The ID of the backup
    date: str  # The date the backup was created
    homeassistant: str  # The version of Home Assistant that created the backup
    name: str  # The name of the backup
    protected: bool  # If the backup is protected
    size: float  # The size of the backup (in bytes)
