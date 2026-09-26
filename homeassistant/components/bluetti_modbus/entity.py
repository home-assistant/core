"""Base entities for the BLUETTI Modbus integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODEL
from .coordinator import BluettiModbusConfigEntry, BluettiModbusDataUpdateCoordinator


def bluetti_modbus_device_info(
    serial: str, sw_version: str | None = None
) -> DeviceInfo:
    """Return device information for a BLUETTI Modbus device."""
    return DeviceInfo(
        identifiers={(DOMAIN, serial)},
        manufacturer="BLUETTI",
        model=MODEL,
        name=MODEL,
        serial_number=serial,
        sw_version=sw_version,
    )


class BluettiModbusEntity(CoordinatorEntity[BluettiModbusDataUpdateCoordinator]):
    """Defines a BLUETTI Modbus entity."""

    _attr_has_entity_name = True

    def __init__(self, *, entry: BluettiModbusConfigEntry, field_name: str) -> None:
        """Initialize a BLUETTI Modbus entity."""
        super().__init__(coordinator=entry.runtime_data.coordinator)
        self._field_name = field_name
        assert (
            entry.unique_id is not None
        )  # the config flow always sets it to the confirmed serial
        self._attr_unique_id = f"{entry.unique_id}_{field_name}"
        self._attr_device_info = entry.runtime_data.device_info
