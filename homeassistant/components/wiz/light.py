"""WiZ integration."""
from __future__ import annotations

import contextlib
import logging
from typing import Any

from pywizlight import PilotBuilder
from pywizlight.bulblibrary import BulbClass, BulbType
from pywizlight.exceptions import WizLightNotKnownBulb
from pywizlight.rgbcw import convertHSfromRGBCW
from pywizlight.scenes import get_id_from_scene_name

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_HS,
    SUPPORT_EFFECT,
    LightEntity,
)
from homeassistant.const import CONF_NAME
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.color as color_utils

from .const import DOMAIN
from .models import WizData

_LOGGER = logging.getLogger(__name__)

DEFAULT_COLOR_MODES = {COLOR_MODE_HS, COLOR_MODE_COLOR_TEMP}


def get_supported_color_modes(bulb_type: BulbType) -> set[str]:
    """Flag supported features."""
    if not bulb_type:
        # fallback
        return DEFAULT_COLOR_MODES
    color_modes = set()
    try:
        features = bulb_type.features
        if features.color:
            color_modes.add(COLOR_MODE_HS)
        if features.color_tmp:
            color_modes.add(COLOR_MODE_COLOR_TEMP)
        if not color_modes and features.brightness:
            color_modes.add(COLOR_MODE_BRIGHTNESS)
        return color_modes
    except WizLightNotKnownBulb:
        _LOGGER.warning("Bulb is not present in the library. Fallback to full feature")
        return DEFAULT_COLOR_MODES


def supports_effects(bulb_type: BulbType) -> bool:
    """Check if a bulb supports effects."""
    with contextlib.suppress(WizLightNotKnownBulb):
        return bool(bulb_type.features.effect)
    return True  # default is true


def get_min_max_mireds(bulb_type: BulbType) -> tuple[int, int]:
    """Return the coldest and warmest color_temp that this light supports."""
    if bulb_type is None:
        return color_utils.color_temperature_kelvin_to_mired(
            6500
        ), color_utils.color_temperature_kelvin_to_mired(2200)
    # DW bulbs have no kelvin
    if bulb_type.bulb_type == BulbClass.DW:
        return 0, 0
    # If bulbtype is TW or RGB then return the kelvin value
    try:
        return color_utils.color_temperature_kelvin_to_mired(
            bulb_type.kelvin_range.max
        ), color_utils.color_temperature_kelvin_to_mired(bulb_type.kelvin_range.min)
    except WizLightNotKnownBulb:
        _LOGGER.debug("Kelvin is not present in the library. Fallback to 6500")
        return color_utils.color_temperature_kelvin_to_mired(
            6500
        ), color_utils.color_temperature_kelvin_to_mired(2200)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the WiZ Platform from config_flow."""
    # Assign configuration variables.
    wiz_data: WizData = hass.data[DOMAIN][entry.entry_id]
    wizbulb = WizBulbEntity(
        wiz_data,
        entry.data[CONF_NAME],
    )
    # Add devices with defined name
    async_add_entities([wizbulb], update_before_add=True)


class WizBulbEntity(CoordinatorEntity, LightEntity):
    """Representation of WiZ Light bulb."""

    def __init__(self, wiz_data: WizData, name: str) -> None:
        """Initialize an WiZLight."""
        super().__init__(wiz_data.coordinator)
        self._light = wiz_data.bulb
        bulb_type: BulbType = self._light.bulbtype
        self._attr_unique_id = self._light.mac
        # new init states
        self._attr_name = name
        self._attr_effect_list = wiz_data.scenes
        self._attr_min_mireds, self._attr_max_mireds = get_min_max_mireds(bulb_type)
        self._attr_supported_color_modes = get_supported_color_modes(bulb_type)
        if supports_effects(bulb_type):
            self._attr_supported_features = SUPPORT_EFFECT
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, self._light.mac)},
            name=name,
            manufacturer="WiZ",
            model=bulb_type.name,
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        return self._light.status

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        if (brightness := self._light.state.get_brightness()) is None:
            return None
        if 0 <= int(brightness) <= 255:
            return int(brightness)
        _LOGGER.error("Received invalid brightness : %s. Expected: 0-255", brightness)
        return None

    @property
    def color_mode(self):
        """Return the current color mode."""
        color_modes = self.supported_color_modes
        if (
            COLOR_MODE_COLOR_TEMP in color_modes
            and self._light.state.get_colortemp() is not None
        ):
            return COLOR_MODE_COLOR_TEMP
        if (
            COLOR_MODE_HS in color_modes
            and (rgb := self._light.state.get_rgb()) is not None
            and rgb[0] is not None
        ):
            return COLOR_MODE_HS
        return COLOR_MODE_BRIGHTNESS

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hs color value."""
        colortemp = self._light.state.get_colortemp()
        if colortemp is not None and colortemp != 0:
            return None
        if (rgb := self._light.state.get_rgb()) is None:
            return None
        if rgb[0] is None:
            # this is the case if the temperature was changed
            # do nothing until the RGB color was changed
            return None
        if (warmwhite := self._light.state.get_warm_white()) is None:
            return None
        return convertHSfromRGBCW(rgb, warmwhite)

    @property
    def color_temp(self) -> int | None:
        """Return the CT color value in mireds."""
        colortemp = self._light.state.get_colortemp()
        if colortemp is None or colortemp == 0:
            return None
        _LOGGER.debug(
            "[wizlight %s] kelvin from the bulb: %s", self._light.ip, colortemp
        )
        return color_utils.color_temperature_kelvin_to_mired(colortemp)

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        return self._light.state.get_scene()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        brightness = None

        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs.get(ATTR_BRIGHTNESS)

        if ATTR_RGB_COLOR in kwargs:
            pilot = PilotBuilder(rgb=kwargs.get(ATTR_RGB_COLOR), brightness=brightness)

        if ATTR_HS_COLOR in kwargs:
            pilot = PilotBuilder(
                hucolor=(kwargs[ATTR_HS_COLOR][0], kwargs[ATTR_HS_COLOR][1]),
                brightness=brightness,
            )
        else:
            colortemp = None
            if ATTR_COLOR_TEMP in kwargs:
                kelvin = color_utils.color_temperature_mired_to_kelvin(
                    kwargs[ATTR_COLOR_TEMP]
                )
                colortemp = kelvin
                _LOGGER.debug(
                    "[wizlight %s] kelvin changed and send to bulb: %s",
                    self._light.ip,
                    colortemp,
                )

            sceneid = None
            if ATTR_EFFECT in kwargs:
                sceneid = get_id_from_scene_name(kwargs[ATTR_EFFECT])

            if sceneid == 1000:  # rhythm
                pilot = PilotBuilder()
            else:
                pilot = PilotBuilder(
                    brightness=brightness, colortemp=colortemp, scene=sceneid
                )
                _LOGGER.debug(
                    "[wizlight %s] Pilot will be send with brightness=%s, colortemp=%s, scene=%s",
                    self._light.ip,
                    brightness,
                    colortemp,
                    sceneid,
                )

            sceneid = None
            if ATTR_EFFECT in kwargs:
                sceneid = get_id_from_scene_name(kwargs[ATTR_EFFECT])

            if sceneid == 1000:  # rhythm
                pilot = PilotBuilder()
            else:
                pilot = PilotBuilder(
                    brightness=brightness, colortemp=colortemp, scene=sceneid
                )

        await self._light.turn_on(pilot)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        await self._light.turn_off()
