"""Light platform for Tween Light Infrared integration."""

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

from .const import CONF_DEVICE_TYPE, CONF_INFRARED_ENTITY_ID, TweenLightIrDeviceType
from .entity import TweenLightIrEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up platform from config entry."""
    if not (infrared_entity_id := entry.data.get(CONF_INFRARED_ENTITY_ID)):
        return

    device_type = entry.data[CONF_DEVICE_TYPE]
    if device_type == TweenLightIrDeviceType.LED_STRIP:
        async_add_entities([TweenLightIrLightEntity(entry, infrared_entity_id)])


class TweenLightIrLightEntity(
    TweenLightIrEntity, InfraredEmitterConsumerEntity, LightEntity
):
    """Represents a Tween Light Infrared light entity."""

    _attr_assumed_state = True
    _attr_color_mode = ColorMode.ONOFF
    _attr_effect_list = [
        "flash",
        "strobe",
        "fade",
        "smooth",
        "red",
        "green",
        "blue",
        "white",
        "tomato",
        "light_green",
        "sky_blue",
        "orange_red",
        "cyan",
        "rebecca_purple",
        "orange",
        "turquoise",
        "purple",
        "yellow",
        "dark_cyan",
        "plum",
    ]
    _attr_name = None
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_translation_key = "led_strip"

    def __init__(self, entry: ConfigEntry, infrared_entity_id: str) -> None:
        """Initialize the entity."""
        super().__init__(entry)
        self._infrared_emitter_entity_id = infrared_entity_id

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn device on."""
        command = TweenLightLEDStripCode.ON.to_command()
        self._attr_is_on = True
        if ATTR_EFFECT in kwargs and kwargs[ATTR_EFFECT] in self._attr_effect_list:
            effect: str = kwargs[ATTR_EFFECT]
            command = TweenLightLEDStripCode[effect.upper()].to_command()

        await self._send_command(command)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._attr_is_on = False
        await self._send_command(TweenLightLEDStripCode.OFF.to_command())
        self.async_write_ha_state()
