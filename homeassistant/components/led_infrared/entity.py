"""Base entity for LED Infrared integration."""

from infrared_protocols.codes.generic.led import Generic13KeyCode, Generic24KeyCode

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, LEDIrDeviceType

CODES: dict[LEDIrDeviceType, type[Generic24KeyCode | Generic13KeyCode]] = {
    LEDIrDeviceType.GENERIC_24_KEY: Generic24KeyCode,
    LEDIrDeviceType.GENERIC_13_KEY: Generic13KeyCode,
}


class LEDIrBaseEntity(Entity):
    """Base entity for LED Infrared."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        device_type: LEDIrDeviceType,
    ) -> None:
        """Initialize the entity."""

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
        )
        self._codes = CODES[device_type]
        self._entry = entry
