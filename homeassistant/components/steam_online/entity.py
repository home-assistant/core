"""Entity classes for the Steam integration."""

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import SteamDataUpdateCoordinator


class SteamEntity(CoordinatorEntity[SteamDataUpdateCoordinator]):
    """Representation of a Steam entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SteamDataUpdateCoordinator,
        steamid: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize a Steam entity."""
        super().__init__(coordinator)
        self._steamid = steamid
        self.entity_description = description
        self._attr_unique_id = f"{steamid}_{description.key}"
        self._attr_device_info = DeviceInfo(
            configuration_url="https://store.steampowered.com",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer=DEFAULT_NAME,
            name=DEFAULT_NAME,
        )
