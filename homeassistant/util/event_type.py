"""Implementation for EventType."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Generic

from typing_extensions import TypeVar

_DataT = TypeVar("_DataT", bound=Mapping[str, Any], default=Mapping[str, Any])


@dataclass(frozen=True)
class EventType(Generic[_DataT]):
    """Custom type for Event.event_type."""

    name: str

    def __hash__(self) -> int:
        """Return hash of name."""
        return hash(self.name)

    def __str__(self) -> str:
        """Return string name."""
        return self.name

    def __len__(self) -> int:
        """Return len of name."""
        return len(self.name)

    def __eq__(self, other: Any) -> bool:
        """Check equality for dict keys to be compatible with str."""
        if isinstance(other, str):
            return self.name == other
        if isinstance(other, EventType):
            return self.name == other.name
        return False
