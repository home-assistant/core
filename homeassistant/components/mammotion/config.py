"""Config storage for Mammotion integration."""

from typing import Any

from pymammotion.data.model.device import MowingDevice

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
        self._pending: dict[str, MowingDevice] = {}
        self._unsaved_changes = False

    async def async_load_mower_data(self) -> None:
        """Load the persisted mower data into memory."""
        self.mower_data = await self.async_load() or {}

    @callback
    def async_update_mower_data(self, device_name: str, data: MowingDevice) -> None:
        """Hold the latest state of a mower; it is serialized when flushed."""
        # Serializing the whole model, map included, on every push is too costly.
        self._pending[device_name] = data

    async def async_flush_mower_data(self, _event: Event | None = None) -> None:
        """Write the latest mower data to disk if it changed."""
        for device_name, device in self._pending.items():
            data = device.to_dict()
            if self.mower_data.get(device_name) != data:
                self.mower_data[device_name] = data
                # Cleared only once saved, so a failed write is retried next flush.
                self._unsaved_changes = True
        self._pending.clear()
        if self._unsaved_changes:
            await self.async_save(dict(self.mower_data))
            self._unsaved_changes = False
