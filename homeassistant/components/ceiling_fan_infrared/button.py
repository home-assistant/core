"""Button platform for the Ceiling Fan Infrared integration."""

from typing import override

from infrared_protocols.codes.generic.ceiling_fan import GenericCeilingFanCode

from homeassistant.components.button import ButtonEntity
from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_INFRARED_ENTITY_ID
from .entity import CeilingFanIrBaseEntity

PARALLEL_UPDATES = 1

BUTTONS = {
    "brightness_up": GenericCeilingFanCode.LIGHT_BRIGHTNESS_UP,
    "brightness_down": GenericCeilingFanCode.LIGHT_BRIGHTNESS_DOWN,
    "color_warmer": GenericCeilingFanCode.LIGHT_COLOR_WARMER,
    "color_cooler": GenericCeilingFanCode.LIGHT_COLOR_COOLER,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the button platform from a config entry."""
    async_add_entities(
        [
            CeilingFanIrButtonEntity(entry, entry.data[CONF_INFRARED_ENTITY_ID], key)
            for key in BUTTONS
        ]
    )


class CeilingFanIrButtonEntity(
    CeilingFanIrBaseEntity, InfraredEmitterConsumerEntity, ButtonEntity
):
    """Represents a key of the ceiling fan remote."""

    def __init__(self, entry: ConfigEntry, infrared_entity_id: str, key: str) -> None:
        """Initialize the entity."""
        super().__init__(entry)
        self._infrared_emitter_entity_id = infrared_entity_id
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._key = key
        self._attr_translation_key = key

    @override
    async def async_press(self) -> None:
        """Send the command for this key."""
        await self._send_command(BUTTONS[self._key].to_command())
