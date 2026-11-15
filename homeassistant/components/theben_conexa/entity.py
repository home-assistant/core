"""Base Entity for the Theben Conexa Smartmeter gateway integration."""

from homeassistant.const import CONF_HOST
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
        raw_serial = coordinator.gateway_info.smgwID.upper()
        # For example convert ETHE0213456789 to E THE02 1345 6789:
        # First char (device type like E for electricity)
        # A block of 3 chars THE (for theben) and 2 digits for production batch
        # two blocks of 4 digits to make it unique
        formatted_serial = " ".join(
            [
                raw_serial[:1],
                raw_serial[1:6],
                *(raw_serial[i : i + 4] for i in range(6, len(raw_serial), 4)),
            ]
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.gateway_info.smgwID)},
            manufacturer="Theben AG",
            model="CONEXA 3.0 Smart Meter Gateway",
            sw_version=coordinator.gateway_info.firmwareVersion,
            serial_number=formatted_serial,
            configuration_url=f"https://{coordinator.config_entry.data[CONF_HOST]}",
        )
