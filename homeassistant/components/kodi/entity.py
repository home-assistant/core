"""Shared entity implementation for Kodi playback."""

from typing import override

from homeassistant.const import CONF_NAME
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import KodiPlaybackCoordinator


class KodiPlaybackEntity(CoordinatorEntity[KodiPlaybackCoordinator]):
    """An entity backed by Kodi playback information."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: KodiPlaybackCoordinator, key: str) -> None:
        """Initialize a playback entity."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        assert entry is not None
        unique_id = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{unique_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer="Kodi",
            name=entry.data[CONF_NAME],
        )

    @property
    @override
    def available(self) -> bool:
        """Return whether stream information is available."""
        return super().available and bool(self.coordinator.data.get("player"))
