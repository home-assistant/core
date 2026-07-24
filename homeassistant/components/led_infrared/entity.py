"""Base entity for LED Infrared integration."""

from infrared_protocols.codes.generic.led import Generic13KeyCode, Generic24KeyCode

from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, LEDIrDeviceType

CODES = {
    LEDIrDeviceType.GENERIC_24_KEY: Generic24KeyCode,
    LEDIrDeviceType.GENERIC_13_KEY: Generic13KeyCode,
}


class LEDIrBaseEntity(InfraredEmitterConsumerEntity):
    """Base entity for LED Infrared."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        device_type: LEDIrDeviceType,
        infrared_entity_id: str,
    ) -> None:
        """Initialize the entity."""

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
        )
        self._infrared_emitter_entity_id = infrared_entity_id
        self._codes = CODES[device_type]
