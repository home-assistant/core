"""Support for Lutron lights."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import CONF_USE_RADIORA_MODE, DOMAIN, LutronData
from .aiolip import Led, LIPLedState, LutronController, Output
from .const import CONF_DEFAULT_DIMMER_LEVEL, DEFAULT_DIMMER_LEVEL
from .entity import LutronKeypadComponent, LutronOutput

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Lutron light platform.

    Add lights from the Main Repeater associated with the config_entry as
    light entities.

    Add keypad leds as light entities. Not if radiora_mode.
    """
    _LOGGER.debug("Setting up Lutron light platform")
    entry_data: LutronData = hass.data[DOMAIN][config_entry.entry_id]
    use_radiora_mode = config_entry.options.get(
        CONF_USE_RADIORA_MODE, config_entry.data.get(CONF_USE_RADIORA_MODE, False)
    )

    async_add_entities(
        (
            LutronLight(device, entry_data.controller, config_entry)
            for device in entry_data.lights
        ),
        True,
    )
    _LOGGER.debug("Lutron light platform setup complete")

    if not use_radiora_mode:
        async_add_entities(
            (
                LutronLedLight(device, entry_data.controller)
                for device in entry_data.leds
            ),
            True,
        )


def to_lutron_level(level):
    """Convert the given Home Assistant light level (0-255) to Lutron (0.0-100.0)."""
    return float((level * 100) / 255)


def to_hass_level(level):
    """Convert the given Lutron (0.0-100.0) light level to Home Assistant (0-255)."""
    return int((level * 255) / 100)


def fade_time_seconds(seconds):
    """Return time seconds for the fade time."""
    if seconds is None:
        return None
    return str(timedelta(seconds=seconds))


class LutronLight(LutronOutput, LightEntity):
    """Representation of a Lutron Light, including dimmable.

    Default fade time in Lutron is 1 sec, if not specified by command
    We are setting 0
    """

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _prev_brightness: int | None = None
    _attr_is_on: bool | None = None

    def __init__(
        self,
        lutron_device: Output,
        controller: LutronController,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the device."""
        super().__init__(lutron_device, controller)
        self._config_entry = config_entry
        if self._lutron_device.is_dimmable:
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            self._attr_supported_features = (
                LightEntityFeature.TRANSITION | LightEntityFeature.FLASH
            )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""

        # if flash := kwargs.get(ATTR_FLASH):
        #     return self._lutron_device.flash(0.5 if flash == "short" else 1.5)
        if ATTR_BRIGHTNESS in kwargs and self._lutron_device.is_dimmable:
            brightness = kwargs[ATTR_BRIGHTNESS]
        elif self._prev_brightness == 0:
            brightness = self._config_entry.options.get(
                CONF_DEFAULT_DIMMER_LEVEL, DEFAULT_DIMMER_LEVEL
            )
        else:
            # light is already on and is not dimmable
            brightness = self._prev_brightness
        self._prev_brightness = brightness
        new_level = to_lutron_level(brightness)
        fade_time = fade_time_seconds(getattr(kwargs, ATTR_TRANSITION, 0))
        await self._execute_device_command(
            self._lutron_device.set_level, new_level, fade_time
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        new_level = 0
        fade_time = fade_time_seconds(getattr(kwargs, ATTR_TRANSITION, 0))
        await self._execute_device_command(
            self._lutron_device.set_level, new_level, fade_time
        )

    async def _request_state(self) -> None:
        """Request the state of the light."""
        await self._execute_device_command(self._lutron_device.get_level)

    def _update_callback(self, value: float):
        """Handle level update for light brightness."""
        # new level for this output
        self._attr_is_on = value > 0
        hass_level = to_hass_level(value)
        self._attr_brightness = hass_level
        if self._prev_brightness is None or hass_level != 0:
            self._prev_brightness = hass_level

        self.async_write_ha_state()


class LutronLedLight(LutronKeypadComponent, LightEntity):
    """Representation of a Lutron Led."""

    _lutron_device: Led
    _attr_is_on: bool | None = None
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_supported_features = LightEntityFeature.FLASH

    def __init__(
        self,
        lutron_device: Led,
        controller: LutronController,
    ) -> None:
        """Initialize the device."""
        super().__init__(lutron_device, controller)
        self._attr_name = lutron_device.name

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        await self._execute_device_command(self._lutron_device.turn_on)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._execute_device_command(self._lutron_device.turn_off)

    async def _request_state(self):
        await self._execute_device_command(self._lutron_device.get_state)

    def _update_callback(self, value: int):
        """Handle device LED state update."""
        self._attr_is_on = value == LIPLedState.ON
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        return {
            "keypad": self.keypad_name,
            "led": self.name,
        }
