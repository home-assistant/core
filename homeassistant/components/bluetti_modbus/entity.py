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


def bluetti_modbus_device_info(unique_id: str, device_type: str) -> DeviceInfo:
    """Return device information for a BLUETTI Modbus device."""
    model = device_name(device_type)
    return DeviceInfo(
        identifiers={(DOMAIN, unique_id)},
        manufacturer="BLUETTI",
        model=model,
        name=model,
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
        self._attr_unique_id = f"{entry.unique_id}_{field_name}"
        self._attr_translation_key = field_name
        self._attr_device_info = entry.runtime_data.device_info
