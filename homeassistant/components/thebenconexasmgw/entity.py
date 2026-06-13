"""Base Entity for the Theben Conexa Smartmeter gateway integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SmgwSensorCoordinator


class ConexaSMGWEntity(CoordinatorEntity[SmgwSensorCoordinator]):
    """Defines a base Theben Conexa Smartmeter gateway entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SmgwSensorCoordinator) -> None:
        """Initialize the Base entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            name=coordinator.gateway_info.smgwID,
            identifiers={(DOMAIN, coordinator.gateway_info.smgwID)},
            manufacturer="Theben AG",
            model="CONEXA 3.0 Smart Meter Gateway",
            sw_version=coordinator.gateway_info.firmwareVersion,
            serial_number=coordinator.gateway_info.smgwID,
            # configuration_url=f"https://{data.host}", TODO: Should I add it? Is it useful? pylint: disable=fixme
        )
