"""Support for esphome domain data."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Self, cast

from bleak_esphome.backend.cache import ESPHomeBluetoothCache

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.json import JSONEncoder

from .const import DOMAIN
from .entry_data import ESPHomeStorage, RuntimeEntryData

STORAGE_VERSION = 1


@dataclass(slots=True)
class DomainData:
    """Define a class that stores global esphome data in hass.data[DOMAIN]."""

    _entry_datas: dict[str, RuntimeEntryData] = field(default_factory=dict)
    _stores: dict[str, ESPHomeStorage] = field(default_factory=dict)
    bluetooth_cache: ESPHomeBluetoothCache = field(
        default_factory=ESPHomeBluetoothCache
    )

    def get_entry_data(self, entry: ConfigEntry) -> RuntimeEntryData:
        """Return the runtime entry data associated with this config entry.

        Raises KeyError if the entry isn't loaded yet.
        """
        return self._entry_datas[entry.entry_id]

    def set_entry_data(self, entry: ConfigEntry, entry_data: RuntimeEntryData) -> None:
        """Set the runtime entry data associated with this config entry."""
        assert entry.entry_id not in self._entry_datas, "Entry data already set!"
        self._entry_datas[entry.entry_id] = entry_data

    def pop_entry_data(self, entry: ConfigEntry) -> RuntimeEntryData:
        """Pop the runtime entry data instance associated with this config entry."""
        return self._entry_datas.pop(entry.entry_id)

    def get_or_create_store(
        self, hass: HomeAssistant, entry: ConfigEntry
    ) -> ESPHomeStorage:
        """Get or create a Store instance for the given config entry."""
        return self._stores.setdefault(
            entry.entry_id,
            ESPHomeStorage(
                hass, STORAGE_VERSION, f"esphome.{entry.entry_id}", encoder=JSONEncoder
            ),
        )

    @classmethod
    def get(cls, hass: HomeAssistant) -> Self:
        """Get the global DomainData instance stored in hass.data."""
        # Don't use setdefault - this is a hot code path
        if DOMAIN in hass.data:
            return cast(Self, hass.data[DOMAIN])
        ret = hass.data[DOMAIN] = cls()
        return ret
