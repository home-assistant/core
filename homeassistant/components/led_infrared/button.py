"""Button platform for LED Infrared integration."""

from typing import override

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_DEVICE_TYPE, CONF_INFRARED_ENTITY_ID, LEDIrDeviceType
from .entity import LEDIrBaseEntity

PARALLEL_UPDATES = 1

SUPPORTED_BUTTONS = {
    LEDIrDeviceType.GENERIC_24_KEY: ["brightness_up", "brightness_down"],
    LEDIrDeviceType.GENERIC_13_KEY: ["brightness_up", "brightness_down", "timer"],
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up platform from config entry."""
    if not (infrared_entity_id := entry.data.get(CONF_INFRARED_ENTITY_ID)):
        return

    async_add_entities(
        [
            LEDIrButtonEntity(
                entry, entry.data[CONF_DEVICE_TYPE], infrared_entity_id, key
            )
            for key in SUPPORTED_BUTTONS.get(entry.data[CONF_DEVICE_TYPE], [])
        ]
    )


class LEDIrButtonEntity(LEDIrBaseEntity, ButtonEntity):
    """Represents a LED Infrared button entity."""

    def __init__(
        self,
        entry: ConfigEntry,
        device_type: LEDIrDeviceType,
        infrared_entity_id: str,
        key: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(entry, device_type, infrared_entity_id)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._key = key
        self._attr_translation_key = key

    @override
    async def async_press(self) -> None:
        """Press the button."""
        await self._send_command(self._codes[self._key.upper()].to_command())
