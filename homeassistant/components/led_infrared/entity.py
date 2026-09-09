"""Base entity for LED Infrared integration."""

from infrared_protocols.codes.generic.led import (
    BaseGenericLEDCode,
    Generic10KeyCode,
    Generic13KeyCode,
    Generic24KeyCode,
    Generic40KeyCode,
    Generic44KeyCode,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, LEDIrDeviceType

CODES: dict[LEDIrDeviceType, type[BaseGenericLEDCode]] = {
    LEDIrDeviceType.GENERIC_10_KEY: Generic10KeyCode,
    LEDIrDeviceType.GENERIC_13_KEY: Generic13KeyCode,
    LEDIrDeviceType.GENERIC_24_KEY: Generic24KeyCode,
    LEDIrDeviceType.GENERIC_40_KEY: Generic40KeyCode,
    LEDIrDeviceType.GENERIC_44_KEY: Generic44KeyCode,
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
