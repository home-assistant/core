"""Storage for iOS CarPlay configuration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util.hass_dict import HassKey

DATA_CARPLAY_STORAGE: HassKey[CarPlayStore] = HassKey("ios_carplay_storage")
STORAGE_VERSION = 1
STORAGE_KEY = "ios.carplay_config"


@dataclass
class CarPlayQuickAccessItem:
    """Quick access item configuration."""

    entity_id: str
    display_name: str | None = None


@dataclass
class CarPlayConfig:
    """CarPlay configuration."""

    enabled: bool = True
    quick_access: list[CarPlayQuickAccessItem] | None = None

    def __post_init__(self) -> None:
        """Initialize defaults."""
        if self.quick_access is None:
            self.quick_access = []


class CarPlayStore:
    """Store for CarPlay configuration."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the CarPlay store."""
        self._hass = hass
        self._store = Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY)
        self._data = CarPlayConfig()

    async def async_load(self) -> None:
        """Load the data from storage."""
        stored_data = await self._store.async_load()
        if stored_data is not None:
            # Convert stored dict back to dataclass
            quick_access = [
                CarPlayQuickAccessItem(**item)
                for item in stored_data.get("quick_access", [])
            ]
            self._data = CarPlayConfig(
                enabled=stored_data.get("enabled", True), quick_access=quick_access
            )

    async def async_save(self) -> None:
        """Save the data to storage."""
        await self._store.async_save(asdict(self._data))

    async def async_set_data(self, data: dict[str, Any]) -> None:
        """Set the carplay data."""
        # Update existing data with new values
        if "enabled" in data:
            self._data.enabled = data["enabled"]
        if "quick_access" in data:
            self._data.quick_access = [
                CarPlayQuickAccessItem(**item) for item in data["quick_access"]
            ]
        await self.async_save()

    def get_data(self) -> dict[str, Any]:
        """Get the carplay data as dict."""
        return asdict(self._data)


def get_carplay_store(hass: HomeAssistant) -> CarPlayStore:
    """Get the CarPlay store."""
    return hass.data[DATA_CARPLAY_STORAGE]
