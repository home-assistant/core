"""Base entity for Spotify."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SpotifyCoordinator


class SpotifyEntity(CoordinatorEntity[SpotifyCoordinator]):
    """Defines a base Spotify entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SpotifyCoordinator) -> None:
        """Initialize the Spotify entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.current_user.user_id)},
            manufacturer="Spotify AB",
            model=f"Spotify {coordinator.current_user.product}",
            name=f"Spotify {coordinator.config_entry.title}",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://open.spotify.com",
        )
