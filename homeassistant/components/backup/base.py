"""Base classes."""

from dataclasses import asdict, dataclass


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
