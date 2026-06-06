"""Switchbot integration light platform."""

from collections.abc import Mapping
import logging
from typing import Any, cast

import switchbot
from switchbot import ColorMode as SwitchBotColorMode, NightLightState

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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity

from .coordinator import SwitchbotConfigEntry, SwitchbotDataUpdateCoordinator
from .entity import SwitchbotEntity, exception_handler

SWITCHBOT_COLOR_MODE_TO_HASS = {
    SwitchBotColorMode.RGB: ColorMode.RGB,
    SwitchBotColorMode.COLOR_TEMP: ColorMode.COLOR_TEMP,
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
    elif isinstance(coordinator.device, switchbot.SwitchbotStandingFan):
        async_add_entities([SwitchbotStandingFanLightEntity(coordinator)])
    else:
        async_add_entities([SwitchbotLightEntity(coordinator)])


class LightExtraStoredData(ExtraStoredData):
    """Object to hold extra stored data."""

    effect: str | None


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
        self._attr_unique_id = f"{coordinator.base_unique_id}_light"

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state:
            self._attr_is_on = last_state.state == STATE_ON

    @property
    def brightness(self) -> int:
        """Return the brightness of the light."""
        return max(0, min(255, round(self._device.brightness * 2.55)))

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the RGB color of the light."""
        return self._device.rgb

    @property
    def is_on(self) -> bool | None:
        """Return true if the light is on."""
        return self._attr_is_on

    @exception_handler
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
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        _LOGGER.debug("Turning off light %s, address %s", kwargs, self._address)
        await self._device.turn_led_off()
        self._attr_is_on = False
        self.async_write_ha_state()


class SwitchbotStandingFanLightEntity(SwitchbotEntity, LightEntity, RestoreEntity):
    """Representation of a Switchbot standing fan light."""

    _device: switchbot.SwitchbotStandingFan
    _attr_translation_key = "standing_fan_light"
    _attr_name = None
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_color_mode = ColorMode.ONOFF
    _attr_effect_list = [
        NightLightState.LEVEL_1.name.lower(),
        NightLightState.LEVEL_2.name.lower(),
    ]
    _attr_effect = _attr_effect_list[0]
    _attr_effect_preference = _attr_effect_list[0]

    def __init__(self, coordinator: SwitchbotDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.base_unique_id}_light"

    @exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        _LOGGER.warning("Turning on light %s, address %s", kwargs, self._address)
        next_effect = self._attr_effect_preference
        if ATTR_EFFECT in kwargs:
            next_effect = kwargs[ATTR_EFFECT]
            self._attr_effect_preference = next_effect

        new_state = NightLightState[next_effect.upper()]
        self._last_run_success = bool(await self._device.set_night_light(new_state))

        self._attr_is_on = True
        self._attr_effect = next_effect
        self.async_write_ha_state()

    @exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        _LOGGER.debug("Turning off light %s, address %s", kwargs, self._address)
        self._last_run_success = bool(
            await self._device.set_night_light(NightLightState.OFF)
        )
        self._attr_is_on = False
        self.async_write_ha_state()

    # @property
    # def is_on(self) -> bool | None:
    #     """Return true if the light is on."""
    #     return self._device.get_night_light_state() != NightLightState.OFF.value

    @property
    def supported_features(self) -> LightEntityFeature:
        """Return supported features."""
        return LightEntityFeature.EFFECT

    @callback
    def _async_update_attrs(self) -> None:
        """Update the entity attributes."""
        night_light_state = NightLightState(self._device.get_night_light_state())
        _LOGGER.debug(
            "Updating light attribute %s, address %s", night_light_state, self._address
        )
        if night_light_state == NightLightState.OFF:
            _LOGGER.debug("Light is off, address %s", self._address)
            self._attr_is_on = False
        else:
            _LOGGER.debug("Light is on, address %s", self._address)
            self._attr_is_on = True
            self._attr_effect = night_light_state.name.lower()

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return the state attributes."""
        retval = {
            **super().extra_state_attributes,
            "effect": self._attr_effect,
            "effect_preference": self._attr_effect_preference,
            "silly": "pants",
        }
        _LOGGER.debug("Extra state attributes %s, address %s", retval, self._address)
        return retval

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._attr_effect = last_state.attributes.get(
                "effect", self._attr_effect_list[0]
            )
            self._attr_effect_preference = last_state.attributes.get(
                "effect_preference", self._attr_effect_list[0]
            )
        _LOGGER.debug("async_adding_to_hass %s", last_state)


class SwitchbotLightEntity(SwitchbotEntity, LightEntity):
    """Representation of switchbot light bulb."""

    _device: switchbot.SwitchbotBaseLight
    _attr_name = None
    _attr_translation_key = "light"

    @property
    def max_color_temp_kelvin(self) -> int:
        """Return the max color temperature."""
        return self._device.max_temp

    @property
    def min_color_temp_kelvin(self) -> int:
        """Return the min color temperature."""
        return self._device.min_temp

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Return the supported color modes."""
        return {SWITCHBOT_COLOR_MODE_TO_HASS[mode] for mode in self._device.color_modes}

    @property
    def supported_features(self) -> LightEntityFeature:
        """Return the supported features."""
        return LightEntityFeature.EFFECT if self.effect_list else LightEntityFeature(0)

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        return max(0, min(255, round(self._device.brightness * 2.55)))

    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        return SWITCHBOT_COLOR_MODE_TO_HASS.get(
            self._device.color_mode, ColorMode.UNKNOWN
        )

    @property
    def effect_list(self) -> list[str] | None:
        """Return the list of effects supported by the light."""
        return self._device.get_effect_list

    @property
    def effect(self) -> str | None:
        """Return the current effect of the light."""
        return self._device.get_effect()

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the RGB color of the light."""
        return self._device.rgb

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature of the light."""
        return self._device.color_temp

    @property
    def is_on(self) -> bool:
        """Return true if the light is on."""
        return self._device.on

    @exception_handler
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
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        _LOGGER.debug("Turning off light %s, address %s", kwargs, self._address)
        await self._device.turn_off()
