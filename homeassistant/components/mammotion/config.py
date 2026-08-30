"""Config storage for Mammotion integration."""

from typing import Any

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .const import DOMAIN

STORAGE_VERSION = 1
STORAGE_MINOR_VERSION = 0


class MammotionConfigStore(Store[dict[str, Any]]):
    """Store the mower state of a single config entry."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize the configuration store."""
        super().__init__(
            hass,
            version=STORAGE_VERSION,
            minor_version=STORAGE_MINOR_VERSION,
            key=f"{DOMAIN}.{entry_id}",
        )
        self.mower_data: dict[str, Any] = {}
        self._dirty = False

    async def async_load_mower_data(self) -> None:
        """Load the persisted mower data into memory."""
        self.mower_data = await self.async_load() or {}

    @callback
    def async_update_mower_data(self, device_name: str, data: dict[str, Any]) -> None:
        """Update a mower in memory; the data is only written on shutdown."""
        if self.mower_data.get(device_name) == data:
            return
        self.mower_data[device_name] = data
        self._dirty = True

    async def async_flush_mower_data(self, _event: Event | None = None) -> None:
        """Write the in-memory mower data to disk if it changed."""
        if not self._dirty:
            return
        self._dirty = False
        await self.async_save(dict(self.mower_data))
