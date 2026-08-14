"""Config storage for Mammotion integration."""

from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .const import DOMAIN

SAVE_DELAY = 300
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
        # In-memory state of the entry's mowers, keyed by device name
        self.mower_data: dict[str, Any] = {}
        self._save_pending = False

    async def async_load_mower_data(self) -> None:
        """Load the persisted mower data into memory."""
        self.mower_data = await self.async_load() or {}

    @callback
    def async_update_mower_data(self, device_name: str, data: dict[str, Any]) -> None:
        """Update a mower in memory, writing to disk at most once per SAVE_DELAY."""
        if self.mower_data.get(device_name) == data:
            return
        self.mower_data[device_name] = data
        # A pending write keeps its own deadline: async_delay_save would push the
        # write back on every call and never fire while polling continues.
        if self._save_pending:
            return
        self._save_pending = True
        self.async_delay_save(self._data_to_save, SAVE_DELAY)

    def _data_to_save(self) -> dict[str, Any]:
        """Return a snapshot to persist; runs in the executor thread."""
        self._save_pending = False
        return dict(self.mower_data)

    async def async_flush_mower_data(self) -> None:
        """Write queued mower data to disk, cancelling the delayed write."""
        if not self._save_pending:
            return
        await self.async_save(self._data_to_save())
