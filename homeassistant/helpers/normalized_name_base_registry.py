"""Provide a base class for registries that use a normalized name index."""

from dataclasses import dataclass
from functools import lru_cache
from typing import TypeVar

from .registry import BaseRegistryItems


@dataclass(slots=True, frozen=True, kw_only=True)
class NormalizedNameBaseRegistryEntry:
    """Normalized Name Base Registry Entry."""

    name: str
    normalized_name: str


_VT = TypeVar("_VT", bound=NormalizedNameBaseRegistryEntry)


@lru_cache(maxsize=1024)
def normalize_name(name: str) -> str:
    """Normalize a name by removing whitespace and case folding."""
    return name.casefold().replace(" ", "")


class NormalizedNameBaseRegistryItems(BaseRegistryItems[_VT]):
    """Base container for normalized name registry items, maps key -> entry.

    Maintains an additional index:
    - normalized name -> entry
    """

    def __init__(self) -> None:
        """Initialize the container."""
        super().__init__()
        self._normalized_names: dict[str, _VT] = {}

    def _unindex_entry(self, key: str, replacement_entry: _VT | None = None) -> None:
        old_entry = self.data[key]
        if (
            replacement_entry is not None
            and (normalized_name := normalize_name(replacement_entry.name))
            != old_entry.normalized_name
            and normalized_name in self._normalized_names
        ):
            raise ValueError(
                f"The name {replacement_entry.name} ({normalized_name}) is already in use"
            )
        del self._normalized_names[old_entry.normalized_name]

    def _index_entry(self, key: str, entry: _VT) -> None:
        self._normalized_names[normalize_name(entry.name)] = entry

    def get_by_name(self, name: str) -> _VT | None:
        """Get entry by name."""
        return self._normalized_names.get(normalize_name(name))
