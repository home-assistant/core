"""Provide a base implementation for registries."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import UserDict
from collections.abc import Mapping, Sequence, ValuesView
from typing import TYPE_CHECKING, Any, Literal

from homeassistant.core import CoreState, HomeAssistant, callback

if TYPE_CHECKING:
    from .storage import Store

SAVE_DELAY = 10
SAVE_DELAY_LONG = 180


class BaseRegistryItems[_DataT](UserDict[str, _DataT], ABC):
    """Base class for registry items."""

    data: dict[str, _DataT]

    def values(self) -> ValuesView[_DataT]:
        """Return the underlying values to avoid __iter__ overhead."""
        return self.data.values()

    @abstractmethod
    def _index_entry(self, key: str, entry: _DataT) -> None:
        """Index an entry."""

    @abstractmethod
    def _unindex_entry(self, key: str, replacement_entry: _DataT | None = None) -> None:
        """Unindex an entry."""

    def __setitem__(self, key: str, entry: _DataT) -> None:
        """Add an item."""
        data = self.data
        if key in data:
            self._unindex_entry(key, entry)
        data[key] = entry
        self._index_entry(key, entry)

    def _unindex_entry_value(
        self, key: str, value: str, index: dict[str, dict[str, Literal[True]]]
    ) -> None:
        """Unindex an entry value.

        key is the entry key
        value is the value to unindex such as config_entry_id or device_id.
        index is the index to unindex from.
        """
        entries = index[value]
        del entries[key]
        if not entries:
            del index[value]

    def __delitem__(self, key: str) -> None:
        """Remove an item."""
        self._unindex_entry(key)
        super().__delitem__(key)


class BaseRegistry[_StoreDataT: Mapping[str, Any] | Sequence[Any]](ABC):
    """Class to implement a registry."""

    hass: HomeAssistant
    _store: Store[_StoreDataT]

    @callback
    def async_schedule_save(self) -> None:
        """Schedule saving the registry."""
        # Schedule the save past startup to avoid writing
        # the file while the system is starting.
        delay = SAVE_DELAY if self.hass.state is CoreState.running else SAVE_DELAY_LONG
        self._store.async_delay_save(self._data_to_save, delay)

    @callback
    @abstractmethod
    def _data_to_save(self) -> _StoreDataT:
        """Return data of registry to store in a file."""
