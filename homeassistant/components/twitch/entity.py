"""Base entity for the Twitch integration."""

from typing import override

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TwitchCoordinator, TwitchUpdate


class TwitchEntity(CoordinatorEntity[TwitchCoordinator]):
    """Base entity for a Twitch channel, with one device per channel."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TwitchCoordinator, channel_id: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.channel_id = channel_id
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, channel_id)},
            manufacturer="Twitch",
            name=coordinator.data[channel_id].name,
        )

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.channel_id in self.coordinator.data

    @property
    def channel(self) -> TwitchUpdate:
        """Return the channel data."""
        return self.coordinator.data[self.channel_id]
