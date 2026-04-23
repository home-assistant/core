"""Support for esphome domain data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.helpers.json import JSONEncoder
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN
from .entry_data import ESPHomeConfigEntry, ESPHomeStorage, RuntimeEntryData

if TYPE_CHECKING:
    from .ffmpeg_proxy import FFmpegProxyData

STORAGE_VERSION = 1

ESPHOME_DATA: HassKey[DomainData] = HassKey(DOMAIN)


@dataclass(slots=True)
class DomainData:
    """Define a class that stores global esphome data."""

    _stores: dict[str, ESPHomeStorage] = field(default_factory=dict)
    ffmpeg_proxy_data: FFmpegProxyData | None = None

    def get_entry_data(self, entry: ESPHomeConfigEntry) -> RuntimeEntryData:
        """Return the runtime entry data associated with this config entry."""
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
    def get(cls, hass: HomeAssistant) -> DomainData:
        """Get the global DomainData instance stored in hass.data."""
        if (data := hass.data.get(ESPHOME_DATA)) is None:
            data = hass.data[ESPHOME_DATA] = cls()
        return data
