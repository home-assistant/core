"""Base entity for the TSUN integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TsunConfigEntry
from .const import DOMAIN, MANUFACTURER
from .coordinator import TsunDataUpdateCoordinator


class TsunEntity(CoordinatorEntity[TsunDataUpdateCoordinator]):
    """Base entity for one TSUN micro-inverter."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: TsunDataUpdateCoordinator, entry: TsunConfigEntry
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        device = coordinator.data.device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device.logger_sn))},
            manufacturer=MANUFACTURER,
            model=device.model,
            name=device.model,
            serial_number=device.inverter_serial_number,
            sw_version=device.firmware_version,
        )
