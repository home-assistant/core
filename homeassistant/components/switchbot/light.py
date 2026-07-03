"""Switchbot integration light platform."""

import logging
from typing import Any, cast, override

import switchbot
from switchbot import ColorMode as SwitchBotColorMode

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .coordinator import SwitchbotConfigEntry, SwitchbotDataUpdateCoordinator
from .entity import SwitchbotEntity, exception_handler

SWITCHBOT_COLOR_MODE_TO_HASS = {
    SwitchBotColorMode.RGB: ColorMode.RGB,
    SwitchBotColorMode.COLOR_TEMP: ColorMode.COLOR_TEMP,
    SwitchBotColorMode.BRIGHTNESS: ColorMode.BRIGHTNESS,
}

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SwitchbotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switchbot light."""
    coordinator = entry.runtime_data
    if isinstance(coordinator.device, switchbot.SwitchbotAirPurifier):
        async_add_entities([SwitchbotAirPurifierLightEntity(coordinator)])
    elif isinstance(coordinator.device, switchbot.SwitchbotCirculatorFanPro):
        async_add_entities([SwitchbotCirculatorFanProLightEntity(coordinator)])
    else:
        async_add_entities([SwitchbotLightEntity(coordinator)])


class SwitchbotAirPurifierLightEntity(SwitchbotEntity, LightEntity, RestoreEntity):
    """Representation of a Switchbot air purifier light."""

    _device: switchbot.SwitchbotAirPurifier
    _attr_translation_key = "air_purifier_light"
    _attr_is_on: bool | None = None
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_color_mode = ColorMode.RGB

    def __init__(self, coordinator: SwitchbotDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.base_unique_id}_light"  # pylint: disable=home-assistant-entity-unique-id-redundant-platform

    @override
    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state:
            self._attr_is_on = last_state.state == STATE_ON

    @property
    @override
    def brightness(self) -> int:
        """Return the brightness of the light."""
        return max(0, min(255, round(self._device.brightness * 2.55)))

    @property
    @override
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the RGB color of the light."""
        return self._device.rgb

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if the light is on."""
        return self._attr_is_on

    @exception_handler
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        _LOGGER.debug("Turning on light %s, address %s", kwargs, self._address)
        brightness = round(
            cast(int, kwargs.get(ATTR_BRIGHTNESS, self.brightness)) / 255 * 100
        )
        if ATTR_RGB_COLOR in kwargs:
            rgb = kwargs[ATTR_RGB_COLOR]
            await self._device.set_rgb(brightness, rgb[0], rgb[1], rgb[2])
            return
        if ATTR_BRIGHTNESS in kwargs:
            await self._device.set_brightness(brightness)
            return
        await self._device.turn_led_on()
        self._attr_is_on = True
        self.async_write_ha_state()

    @exception_handler
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        _LOGGER.debug("Turning off light %s, address %s", kwargs, self._address)
        await self._device.turn_led_off()
        self._attr_is_on = False
        self.async_write_ha_state()


class SwitchbotLightEntity(SwitchbotEntity, LightEntity):
    """Representation of switchbot light bulb."""

    _device: switchbot.SwitchbotBaseLight
    _attr_name = None
    _attr_translation_key = "light"

    @property
    @override
    def max_color_temp_kelvin(self) -> int:
        """Return the max color temperature."""
        return self._device.max_temp

    @property
    @override
    def min_color_temp_kelvin(self) -> int:
        """Return the min color temperature."""
        return self._device.min_temp

    @property
    @override
    def supported_color_modes(self) -> set[ColorMode]:
        """Return the supported color modes."""
        return {SWITCHBOT_COLOR_MODE_TO_HASS[mode] for mode in self._device.color_modes}

    @property
    @override
    def supported_features(self) -> LightEntityFeature:
        """Return the supported features."""
        return LightEntityFeature.EFFECT if self.effect_list else LightEntityFeature(0)

    @property
    @override
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        return max(0, min(255, round(self._device.brightness * 2.55)))

    @property
    @override
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        return SWITCHBOT_COLOR_MODE_TO_HASS.get(
            self._device.color_mode, ColorMode.UNKNOWN
        )

    @property
    @override
    def effect_list(self) -> list[str] | None:
        """Return the list of effects supported by the light."""
        return self._device.get_effect_list

    @property
    @override
    def effect(self) -> str | None:
        """Return the current effect of the light."""
        return self._device.get_effect()

    @property
    @override
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the RGB color of the light."""
        return self._device.rgb

    @property
    @override
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature of the light."""
        return self._device.color_temp

    @property
    @override
    def is_on(self) -> bool:
        """Return true if the light is on."""
        return self._device.on

    @exception_handler
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        _LOGGER.debug("Turning on light %s, address %s", kwargs, self._address)
        brightness = round(
            cast(int, kwargs.get(ATTR_BRIGHTNESS, self.brightness)) / 255 * 100
        )

        if (
            self.supported_color_modes
            and ColorMode.COLOR_TEMP in self.supported_color_modes
            and ATTR_COLOR_TEMP_KELVIN in kwargs
        ):
            kelvin = max(2700, min(6500, kwargs[ATTR_COLOR_TEMP_KELVIN]))
            await self._device.set_color_temp(brightness, kelvin)
            return
        if ATTR_EFFECT in kwargs:
            effect = kwargs[ATTR_EFFECT]
            await self._device.set_effect(effect)
            return
        if ATTR_RGB_COLOR in kwargs:
            rgb = kwargs[ATTR_RGB_COLOR]
            await self._device.set_rgb(brightness, rgb[0], rgb[1], rgb[2])
            return
        if ATTR_BRIGHTNESS in kwargs:
            await self._device.set_brightness(brightness)
            return
        await self._device.turn_on()

    @exception_handler
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        _LOGGER.debug("Turning off light %s, address %s", kwargs, self._address)
        await self._device.turn_off()


class SwitchbotCirculatorFanProLightEntity(SwitchbotEntity, LightEntity):
    """Two-level night light of a Circulator Fan Pro.

    The night light has two brightness levels (high / low), mapped onto HA
    brightness: > 50% selects the high level, otherwise low.
    """

    _device: switchbot.SwitchbotCirculatorFanPro
    _attr_translation_key = "circulator_fan_pro_light"
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if the night light is on."""
        return self._device.is_night_light_on()

    @property
    @override
    def brightness(self) -> int | None:
        """Return HA brightness for the night light's two hardware levels.

        The device reports level 1 (high) or level 2 (low); these map to HA
        brightness 255 and 128 respectively. Returns None when unavailable.
        """
        level = self._device.get_night_light_level()
        if not level:
            return None
        return 128 if level == 2 else 255

    @exception_handler
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the night light on (picking high/low from the requested brightness)."""
        _LOGGER.debug("Turning on night light %s, address %s", kwargs, self._address)
        low = (
            requested := kwargs.get(ATTR_BRIGHTNESS)
        ) is not None and requested <= 128
        await self._device.turn_on_light(low=low)

    @exception_handler
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the night light off."""
        _LOGGER.debug("Turning off night light %s, address %s", kwargs, self._address)
        await self._device.turn_off_light()
