"""Models for the backup integration."""

from dataclasses import asdict, dataclass


@dataclass()
class AgentBackup:
    """Base backup class."""

    backup_id: str
    date: str
    name: str
    protected: bool
    size: int

    def as_dict(self) -> dict:
        """Return a dict representation of this backup."""
        return asdict(self)
