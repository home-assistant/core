"""Support for esphome domain data."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache
from typing import Self

from homeassistant.core import HomeAssistant
from homeassistant.helpers.json import JSONEncoder

from .const import DOMAIN
from .entry_data import ESPHomeConfigEntry, ESPHomeStorage, RuntimeEntryData

STORAGE_VERSION = 1


@dataclass(slots=True)
class DomainData:
    """Define a class that stores global esphome data in hass.data[DOMAIN]."""

    _stores: dict[str, ESPHomeStorage] = field(default_factory=dict)

    def get_entry_data(self, entry: ESPHomeConfigEntry) -> RuntimeEntryData:
        """Return the runtime entry data associated with this config entry.

        Raises KeyError if the entry isn't loaded yet.
        """
        return entry.runtime_data

    def get_or_create_store(
        self, hass: HomeAssistant, entry: ESPHomeConfigEntry
    ) -> ESPHomeStorage:
        """Get or create a Store instance for the given config entry."""
        return self._stores.setdefault(
            entry.entry_id,
            ESPHomeStorage(
                hass, STORAGE_VERSION, f"esphome.{entry.entry_id}", encoder=JSONEncoder
            ),
        )

    @classmethod
    @cache
    def get(cls, hass: HomeAssistant) -> Self:
        """Get the global DomainData instance stored in hass.data."""
        ret = hass.data[DOMAIN] = cls()
        return ret
