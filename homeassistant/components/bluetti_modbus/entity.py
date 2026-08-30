"""Base entities for the BLUETTI Modbus integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_TYPE_BALCO260, DEVICE_TYPE_EP2000, DOMAIN
from .coordinator import BluettiModbusConfigEntry, BluettiModbusDataUpdateCoordinator

_MODEL_NAMES = {
    DEVICE_TYPE_BALCO260: "Balco260",
    DEVICE_TYPE_EP2000: "EP2000",
}


def device_name(device_type: str) -> str:
    """Return the model name a device type reads like in the UI."""
    return _MODEL_NAMES.get(device_type, "BLUETTI power station")


def bluetti_modbus_device_info(
    entry_id: str,
    device_type: str,
    serial: str | None,
    sw_version: str | None = None,
) -> DeviceInfo:
    """Return device information for a BLUETTI Modbus device.

    serial is entry.unique_id, not a fresh register read - the same value
    confirmed at config-flow time, before this device would otherwise be
    shown as a plain sensor. Identity keys on it where the model reports one
    (Balco260), falling back to entry_id only for a model with no serial
    field over Modbus (EP2000).

    sw_version is the raw ARM/DSP firmware values as reported (see
    __init__.py's caller) - real values, not decoded into a version scheme
    that isn't documented anywhere, but device identity rather than a
    measurement, so it belongs here rather than as a sensor.
    """
    model = device_name(device_type)
    return DeviceInfo(
        identifiers={(DOMAIN, serial or entry_id)},
        manufacturer="BLUETTI",
        model=model,
        name=model,
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
        # entry.unique_id is the confirmed serial where the model reports one
        # (Balco260); entry_id is the fallback for one that doesn't (EP2000).
        self._attr_unique_id = f"{entry.unique_id or entry.entry_id}_{field_name}"
        self._attr_translation_key = field_name
        self._attr_device_info = entry.runtime_data.device_info
