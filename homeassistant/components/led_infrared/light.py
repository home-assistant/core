"""Light platform for LED Infrared integration."""

from typing import Any

from infrared_protocols.codes.tween_light.led_strip import TweenLightLEDStripCode

from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.components.light import (
    ATTR_EFFECT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_DEVICE_TYPE,
    CONF_INFRARED_ENTITY_ID,
    SUPPORTED_COLORS,
    SUPPORTED_EFFECTS,
    LEDIrDeviceType,
)
from .entity import LEDIrEntity

PARALLEL_UPDATES = 1

CODES = {
    LEDIrDeviceType.GENERIC_24_KEY: TweenLightLEDStripCode,
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
        [LEDIrLightEntity(entry, entry.data[CONF_DEVICE_TYPE], infrared_entity_id)]
    )


class LEDIrLightEntity(LEDIrEntity, InfraredEmitterConsumerEntity, LightEntity):
    """Represents a LED Infrared light entity."""

    _attr_assumed_state = True
    _attr_color_mode = ColorMode.ONOFF
    _attr_effect_list: list[str]
    _attr_name = None
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_translation_key = "light"

    def __init__(
        self,
        entry: ConfigEntry,
        device_type: LEDIrDeviceType,
        infrared_entity_id: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(entry)
        self._infrared_emitter_entity_id = infrared_entity_id

        self._codes = CODES[device_type]
        self._attr_effect_list = (
            SUPPORTED_EFFECTS[device_type] + SUPPORTED_COLORS[device_type]
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn device on."""
        command = self._codes.ON.to_command()
        self._attr_is_on = True
        if ATTR_EFFECT in kwargs and kwargs[ATTR_EFFECT] in self._attr_effect_list:
            effect: str = kwargs[ATTR_EFFECT]
            command = self._codes[effect.upper()].to_command()

        await self._send_command(command)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._attr_is_on = False
        await self._send_command(self._codes.OFF.to_command())
        self.async_write_ha_state()
