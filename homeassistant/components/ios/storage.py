"""Storage for iOS CarPlay configuration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util.hass_dict import HassKey

DATA_CARPLAY_STORAGE: HassKey[CarPlayStore] = HassKey("ios_carplay_storage")
STORAGE_VERSION = 1
STORAGE_KEY = "ios.carplay_config"


class CarPlayStore:
    """Store for CarPlay configuration."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the CarPlay store."""
        self.hass = hass
        self._store = Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY)
        self.data: dict[str, Any] = {}
        self.subscriptions: dict[str | None, list[Callable[[], None]]] = {}
        self._loaded = False

    async def async_load(self) -> None:
        """Load the data from storage."""
        if self._loaded:
            return

        stored_data = await self._store.async_load()
        if stored_data is not None:
            self.data = stored_data
        else:
            # Default carplay configuration
            self.data = {
                "enabled": True,
                "quick_access": [],
            }
        self._loaded = True

    async def async_save(self) -> None:
        """Save the data to storage."""
        await self._store.async_save(self.data)
        # Notify subscribers of changes
        for cb in self.subscriptions.get(None, []):
            cb()

    async def async_set_data(self, data: dict[str, Any]) -> None:
        """Set the carplay data."""
        await self.async_load()
        self.data.update(data)
        await self.async_save()

    async def async_get_data(self) -> dict[str, Any]:
        """Get the carplay data."""
        await self.async_load()
        return self.data.copy()

    async def async_set_enabled(self, enabled: bool) -> None:
        """Set the carplay enabled state."""
        await self.async_load()
        self.data["enabled"] = enabled
        await self.async_save()

    async def async_set_quick_access(self, quick_access: list[dict[str, Any]]) -> None:
        """Set the carplay quick access items."""
        await self.async_load()
        self.data["quick_access"] = quick_access
        await self.async_save()

    @callback
    def async_subscribe(
        self, on_update_callback: Callable[[], None]
    ) -> Callable[[], None]:
        """Subscribe to data changes."""
        self.subscriptions.setdefault(None, []).append(on_update_callback)

        def unsubscribe() -> None:
            """Unsubscribe from the store."""
            self.subscriptions[None].remove(on_update_callback)

        return unsubscribe


def get_carplay_store(hass: HomeAssistant) -> CarPlayStore:
    """Get the CarPlay store."""
    return hass.data[DATA_CARPLAY_STORAGE]
