"""Light platform for the Ceiling Fan Infrared integration."""

from typing import Any, override

from infrared_protocols.codes.generic.ceiling_fan import GenericCeilingFanCode

from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_INFRARED_ENTITY_ID
from .entity import CeilingFanIrBaseEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the light platform from a config entry."""
    async_add_entities(
        [CeilingFanIrLightEntity(entry, entry.data[CONF_INFRARED_ENTITY_ID])]
    )


class CeilingFanIrLightEntity(
    CeilingFanIrBaseEntity, InfraredEmitterConsumerEntity, LightEntity
):
    """Represents a ceiling fan light controlled through an infrared emitter.

    The remote only has a toggle key for the light, so turning on and off send
    the same command and the state is assumed.
    """

    _attr_assumed_state = True
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_translation_key = "light"

    def __init__(self, entry: ConfigEntry, infrared_entity_id: str) -> None:
        """Initialize the entity."""
        super().__init__(entry)
        self._infrared_emitter_entity_id = infrared_entity_id
        self._attr_unique_id = f"{entry.entry_id}_toggle"

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Toggle the light on."""
        await self._send_command(GenericCeilingFanCode.LIGHT_TOGGLE.to_command())
        self._attr_is_on = True
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Toggle the light off."""
        await self._send_command(GenericCeilingFanCode.LIGHT_TOGGLE.to_command())
        self._attr_is_on = False
        self.async_write_ha_state()
