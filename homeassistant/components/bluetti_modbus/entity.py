"""Base entities for the BLUETTI Modbus integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BluettiModbusConfigEntry, BluettiModbusDataUpdateCoordinator

_MODEL_NAME = "Balco260"


def bluetti_modbus_device_info(
    serial: str, sw_version: str | None = None
) -> DeviceInfo:
    """Return device information for a BLUETTI Modbus device.

    serial is entry.unique_id, not a fresh register read - the same value
    confirmed at config-flow time, before this device would otherwise be
    shown as a plain sensor.

    sw_version is the raw ARM/DSP firmware values as reported (see
    __init__.py's caller) - real values, not decoded into a version scheme
    that isn't documented anywhere, but device identity rather than a
    measurement, so it belongs here rather than as a sensor.
    """
    return DeviceInfo(
        identifiers={(DOMAIN, serial)},
        manufacturer="BLUETTI",
        model=_MODEL_NAME,
        name=_MODEL_NAME,
        serial_number=serial,
        sw_version=sw_version,
    )


class BluettiModbusEntity(CoordinatorEntity[BluettiModbusDataUpdateCoordinator]):
    """Defines a BLUETTI Modbus entity.

    The device reads a fixed register map decided at dev time (unlike the
    cloud integration, whose sensors are named by whatever the BLUETTI cloud
    API reports at runtime), so every entity here gets a real translation key.
    """

    _attr_has_entity_name = True

    def __init__(self, *, entry: BluettiModbusConfigEntry, field_name: str) -> None:
        """Initialize a BLUETTI Modbus entity."""
        super().__init__(coordinator=entry.runtime_data.coordinator)
        self._field_name = field_name
        assert (
            entry.unique_id is not None
        )  # the config flow always sets it to the confirmed serial
        self._attr_unique_id = f"{entry.unique_id}_{field_name}"
        self._attr_translation_key = field_name
        self._attr_device_info = entry.runtime_data.device_info
