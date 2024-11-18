"""Entity classes for the Steam integration."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import SteamDataUpdateCoordinator


class SteamEntity(CoordinatorEntity[SteamDataUpdateCoordinator]):
    """Representation of a Steam entity."""

    _attr_attribution = "Data provided by Steam"

    def __init__(self, coordinator: SteamDataUpdateCoordinator) -> None:
        """Initialize a Steam entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            configuration_url="https://store.steampowered.com",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer=DEFAULT_NAME,
            name=DEFAULT_NAME,
        )
