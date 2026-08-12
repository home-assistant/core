"""Light platform for LED Infrared integration."""

from typing import Any, override

from infrared_protocols.codes.generic.led import Generic13KeyCode, Generic24KeyCode

from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.components.light import (
    ATTR_EFFECT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_DEVICE_TYPE, CONF_INFRARED_ENTITY_ID, DOMAIN, LEDIrDeviceType

PARALLEL_UPDATES = 1

CODES = {
    LEDIrDeviceType.GENERIC_24_KEY: Generic24KeyCode,
    LEDIrDeviceType.GENERIC_13_KEY: Generic13KeyCode,
}


SUPPORTED_EFFECTS = {
    LEDIrDeviceType.GENERIC_24_KEY: ["flash", "strobe", "fade", "smooth"],
    LEDIrDeviceType.GENERIC_13_KEY: [
        "mode_1",
        "mode_2",
        "mode_3",
        "mode_4",
        "mode_5",
        "mode_6",
        "mode_7",
        "mode_8",
    ],
}


SUPPORTED_COLORS = {
    LEDIrDeviceType.GENERIC_24_KEY: [
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
    ],
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


class LEDIrLightEntity(InfraredEmitterConsumerEntity, LightEntity):
    """Represents a LED Infrared light entity."""

    _attr_assumed_state = True
    _attr_color_mode = ColorMode.ONOFF
    _attr_effect_list: list[str]
    _attr_has_entity_name = True
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
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
        )

        self._infrared_emitter_entity_id = infrared_entity_id

        self._codes = CODES[device_type]
        self._attr_effect_list = SUPPORTED_EFFECTS.get(
            device_type, []
        ) + SUPPORTED_COLORS.get(device_type, [])

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn device on."""
        await self._send_command(self._codes.ON.to_command())
        self._attr_is_on = True
        effect: str | None = kwargs.get(ATTR_EFFECT)
        if effect and effect in self._attr_effect_list:
            await self._send_command(self._codes[effect.upper()].to_command())
            self._attr_effect = effect

        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._send_command(self._codes.OFF.to_command())
        self._attr_is_on = False
        self.async_write_ha_state()
