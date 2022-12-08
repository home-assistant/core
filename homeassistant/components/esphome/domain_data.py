"""Support for esphome domain data."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeVar, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.json import JSONEncoder
from homeassistant.helpers.storage import Store

from .entry_data import RuntimeEntryData

STORAGE_VERSION = 1
DOMAIN = "esphome"

_DomainDataSelfT = TypeVar("_DomainDataSelfT", bound="DomainData")


@dataclass
class DomainData:
    """Define a class that stores global esphome data in hass.data[DOMAIN]."""

    _entry_datas: dict[str, RuntimeEntryData] = field(default_factory=dict)
    _stores: dict[str, Store] = field(default_factory=dict)
    _entry_by_unique_id: dict[str, ConfigEntry] = field(default_factory=dict)

    def get_by_unique_id(self, unique_id: str) -> ConfigEntry:
        """Get the config entry by its unique ID."""
        return self._entry_by_unique_id[unique_id]

    def get_entry_data(self, entry: ConfigEntry) -> RuntimeEntryData:
        """Return the runtime entry data associated with this config entry.

        Raises KeyError if the entry isn't loaded yet.
        """
        return self._entry_datas[entry.entry_id]

    def set_entry_data(self, entry: ConfigEntry, entry_data: RuntimeEntryData) -> None:
        """Set the runtime entry data associated with this config entry."""
        if entry.entry_id in self._entry_datas:
            raise ValueError("Entry data for this entry is already set")
        self._entry_datas[entry.entry_id] = entry_data
        if entry.unique_id:
            self._entry_by_unique_id[entry.unique_id] = entry

    def pop_entry_data(self, entry: ConfigEntry) -> RuntimeEntryData:
        """Pop the runtime entry data instance associated with this config entry."""
        if entry.unique_id:
            del self._entry_by_unique_id[entry.unique_id]
        return self._entry_datas.pop(entry.entry_id)

    def is_entry_loaded(self, entry: ConfigEntry) -> bool:
        """Check whether the given entry is loaded."""
        return entry.entry_id in self._entry_datas

    def get_or_create_store(self, hass: HomeAssistant, entry: ConfigEntry) -> Store:
        """Get or create a Store instance for the given config entry."""
        return self._stores.setdefault(
            entry.entry_id,
            Store(
                hass, STORAGE_VERSION, f"esphome.{entry.entry_id}", encoder=JSONEncoder
            ),
        )

    @classmethod
    def get(cls: type[_DomainDataSelfT], hass: HomeAssistant) -> _DomainDataSelfT:
        """Get the global DomainData instance stored in hass.data."""
        # Don't use setdefault - this is a hot code path
        if DOMAIN in hass.data:
            return cast(_DomainDataSelfT, hass.data[DOMAIN])
        ret = hass.data[DOMAIN] = cls()
        return ret
