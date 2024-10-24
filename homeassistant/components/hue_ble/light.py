"""light platform."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from HueBLE import HueBleLight

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_XY_COLOR,
    ColorMode,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


if TYPE_CHECKING:
    from . import HueBLEConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HueBLEConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add light for passed config_entry in HA."""

    light = config_entry.runtime_data
    async_add_entities([HaHueBLE(light)])


class HaHueBLE(LightEntity):
    """Representation of a light."""

    entity_description = LightEntityDescription(
        key="hue_light", has_entity_name=True, name=None
    )

    def __init__(self, api: HueBleLight) -> None:
        """Initialize the light object. Does not connect."""

        self._light = api
        self._name = self._light.name
        self._address = self._light.address
        self._attr_unique_id = self._light.address
        self._attr_min_mireds = self._light.minimum_mireds
        self._attr_max_mireds = self._light.maximum_mireds
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, self._light.address)},
            manufacturer=self._light.manufacturer,
            model=self._light.model,
            sw_version=self._light.firmware,
        )

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""

        self._light.add_callback_on_state_changed(self._state_change_callback)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from HA."""

        self._light.remove_callback(self._state_change_callback)

    def _state_change_callback(self) -> None:
        """Run when light informs of state update. Updates local properties."""

        _LOGGER.debug("Received state notification from light %s", self._name)
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Is light available."""
        return self._light.available

    @property
    def is_on(self) -> bool:
        """Is light on."""
        return self._light.power_state

    @property
    def brightness(self) -> int:
        """Light brightness."""
        return self._light.brightness

    @property
    def color_temp(self) -> int:
        """Light color temperature in mireds."""
        return self._light.colour_temp

    @property
    def xy_color(self) -> tuple[float, float]:
        """XY color of light."""
        return self._light.colour_xy

    async def async_update(self) -> None:
        """Fetch latest state from light and make available via properties."""
        await self._light.poll_state(run_callbacks=True)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set properties then turn the light on."""

        _LOGGER.debug("Turning light %s on with args %s", self.name, kwargs)

        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            _LOGGER.debug("Setting brightness of %s to %s", self.name, brightness)
            await self._light.set_brightness(brightness)

        if ATTR_COLOR_TEMP in kwargs:
            mireds = kwargs[ATTR_COLOR_TEMP]
            _LOGGER.debug("Setting color temp of %s to %s", self.name, mireds)
            await self._light.set_colour_temp(mireds)

        if ATTR_XY_COLOR in kwargs:
            xy_color = kwargs[ATTR_XY_COLOR]
            _LOGGER.debug("Setting XY color of %s to %s", self.name, xy_color)
            await self._light.set_colour_xy(xy_color[0], xy_color[1])

        await self._light.set_power(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn light off then set properties."""

        _LOGGER.debug("Turning light %s off with args %s", self.name, kwargs)

        await self._light.set_power(False)

        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            _LOGGER.debug("Setting brightness of %s to %s", self.name, brightness)
            await self._light.set_brightness(brightness)

        if ATTR_COLOR_TEMP in kwargs:
            mireds = kwargs[ATTR_COLOR_TEMP]
            _LOGGER.debug("Setting color temp of %s to %s", self.name, mireds)
            await self._light.set_colour_temp(mireds)

        if ATTR_XY_COLOR in kwargs:
            xy_color = kwargs[ATTR_XY_COLOR]
            _LOGGER.debug("Setting XY color of %s to %s", self.name, xy_color)
            await self._light.set_colour_xy(xy_color[0], xy_color[1])

    @property
    def supported_color_modes(self) -> set[ColorMode] | None:
        """Flag supported color modes."""

        supported_modes = set()

        if self._light.supports_colour_xy:
            supported_modes.add(ColorMode.XY)

        if self._light.supports_colour_temp:
            supported_modes.add(ColorMode.COLOR_TEMP)

        if self._light.supports_brightness and len(supported_modes) == 0:
            supported_modes.add(ColorMode.BRIGHTNESS)

        if self._light.supports_on_off and len(supported_modes) == 0:
            supported_modes.add(ColorMode.ONOFF)

        if len(supported_modes) == 0:
            supported_modes.add(ColorMode.UNKNOWN)

        return supported_modes

    @property
    def color_mode(self) -> ColorMode | None:
        """Color mode of the light."""

        if self._light.supports_colour_xy:
            if self._light.supports_colour_temp and self._light.colour_temp_mode:
                return ColorMode.COLOR_TEMP
            return ColorMode.XY

        if self._light.supports_brightness:
            return ColorMode.BRIGHTNESS

        if self._light.supports_on_off:
            return ColorMode.ONOFF

        return ColorMode.UNKNOWN

    @property
    def should_poll(self) -> bool:
        """Poll if light offline to trigger auto retry."""
        return not self.available
