"""Provide a base class for registries that use a normalized name index."""
from collections import UserDict
from collections.abc import ValuesView
from dataclasses import dataclass
from typing import TypeVar


@dataclass(slots=True, frozen=True, kw_only=True)
class NormalizedNameBaseRegistryEntry:
    """Normalized Name Base Registry Entry."""

    name: str
    normalized_name: str


_VT = TypeVar("_VT", bound=NormalizedNameBaseRegistryEntry)


def normalize_name(name: str) -> str:
    """Normalize a name by removing whitespace and case folding."""
    return name.casefold().replace(" ", "")


class NormalizedNameBaseRegistryItems(UserDict[str, _VT]):
    """Base container for normalized name registry items, maps key -> entry.

    Maintains an additional index:
    - normalized name -> entry
    """

    def __init__(self) -> None:
        """Initialize the container."""
        super().__init__()
        self._normalized_names: dict[str, _VT] = {}

    def values(self) -> ValuesView[_VT]:
        """Return the underlying values to avoid __iter__ overhead."""
        return self.data.values()

    def __setitem__(self, key: str, entry: _VT) -> None:
        """Add an item."""
        data = self.data
        normalized_name = normalize_name(entry.name)

        if key in data:
            old_entry = data[key]
            if (
                normalized_name != old_entry.normalized_name
                and normalized_name in self._normalized_names
            ):
                raise ValueError(
                    f"The name {entry.name} ({normalized_name}) is already in use"
                )
            del self._normalized_names[old_entry.normalized_name]
        data[key] = entry
        self._normalized_names[normalized_name] = entry

    def __delitem__(self, key: str) -> None:
        """Remove an item."""
        entry = self[key]
        normalized_name = normalize_name(entry.name)
        del self._normalized_names[normalized_name]
        super().__delitem__(key)

    def get_by_name(self, name: str) -> _VT | None:
        """Get entry by name."""
        return self._normalized_names.get(normalize_name(name))
