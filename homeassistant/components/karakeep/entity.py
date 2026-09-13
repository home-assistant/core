"""Base entity for the Karakeep integration."""

from homeassistant.const import CONF_URL
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import KarakeepDataUpdateCoordinator


class KarakeepEntity(CoordinatorEntity[KarakeepDataUpdateCoordinator]):
    """Base class for Karakeep entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: KarakeepDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        url = coordinator.config_entry.data[CONF_URL]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer="Karakeep",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=url,
            sw_version=coordinator.version,
        )
