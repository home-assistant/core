"""Base entity for VegeHub."""

from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import VegeHubCoordinator


class VegeHubEntity(CoordinatorEntity[VegeHubCoordinator]):
    """Defines a base VegeHub entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: VegeHubCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        config_entry = coordinator.config_entry
        self._mac_address = config_entry.data[CONF_MAC]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._mac_address)},
            name=config_entry.data[CONF_HOST],
            manufacturer=MANUFACTURER,
            model=MODEL,
            connections={(CONNECTION_NETWORK_MAC, self._mac_address)},
            sw_version=coordinator.vegehub.sw_version,
            configuration_url=coordinator.vegehub.url,
        )
