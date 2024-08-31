"""Support for Vera lights."""

from __future__ import annotations

from typing import Any

import pyvera as veraApi

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ENTITY_ID_FORMAT,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.color as color_util

from . import VeraDevice
from .common import ControllerData, get_controller_data


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor config entry."""
    controller_data = get_controller_data(hass, entry)
    async_add_entities(
        [
            VeraLight(device, controller_data)
            for device in controller_data.devices[Platform.LIGHT]
        ],
        True,
    )


class VeraLight(VeraDevice[veraApi.VeraDimmer], LightEntity):
    """Representation of a Vera Light, including dimmable."""

    _attr_is_on = False
    _attr_hs_color: tuple[float, float] | None = None
    _attr_brightness: int | None = None

    def __init__(
        self, vera_device: veraApi.VeraDimmer, controller_data: ControllerData
    ) -> None:
        """Initialize the light."""
        VeraDevice.__init__(self, vera_device, controller_data)
        self.entity_id = ENTITY_ID_FORMAT.format(self.vera_id)

    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        if self.vera_device.is_dimmable:
            if self._attr_hs_color:
                return ColorMode.HS
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Flag supported color modes."""
        return {self.color_mode}

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        if ATTR_HS_COLOR in kwargs and self._attr_hs_color:
            rgb = color_util.color_hs_to_RGB(*kwargs[ATTR_HS_COLOR])
            self.vera_device.set_color(rgb)
        elif ATTR_BRIGHTNESS in kwargs and self.vera_device.is_dimmable:
            self.vera_device.set_brightness(kwargs[ATTR_BRIGHTNESS])
        else:
            self.vera_device.switch_on()

        self._attr_is_on = True
        self.schedule_update_ha_state(True)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        self.vera_device.switch_off()
        self._attr_is_on = False
        self.schedule_update_ha_state()

    def update(self) -> None:
        """Call to update state."""
        super().update()
        self._attr_is_on = self.vera_device.is_switched_on()
        if self.vera_device.is_dimmable:
            # If it is dimmable, both functions exist. In case color
            # is not supported, it will return None
            self._attr_brightness = self.vera_device.get_brightness()
            rgb = self.vera_device.get_color()
            self._attr_hs_color = color_util.color_RGB_to_hs(*rgb) if rgb else None
