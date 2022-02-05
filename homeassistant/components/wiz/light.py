"""WiZ integration."""
from __future__ import annotations

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
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
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

DEFAULT_SUPPORTED_FEATURES = (
    SUPPORT_BRIGHTNESS | SUPPORT_COLOR | SUPPORT_COLOR_TEMP | SUPPORT_EFFECT
)


def get_supported_features(bulb_type: BulbType) -> int:
    """Flag supported features."""
    if not bulb_type:
        # fallback
        return DEFAULT_SUPPORTED_FEATURES
    features = 0
    try:
        # Map features for better reading
        if bulb_type.features.brightness:
            features |= SUPPORT_BRIGHTNESS
        if bulb_type.features.color:
            features |= SUPPORT_COLOR
        if bulb_type.features.effect:
            features |= SUPPORT_EFFECT
        if bulb_type.features.color_tmp:
            features |= SUPPORT_COLOR_TEMP
        return features
    except WizLightNotKnownBulb:
        _LOGGER.warning("Bulb is not present in the library. Fallback to full feature")
        return DEFAULT_SUPPORTED_FEATURES


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
        self._attr_supported_features = get_supported_features(bulb_type)
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
    def hs_color(self):
        """Return the hs color value."""
        colortemp = self._light.state.get_colortemp()
        if colortemp is not None and colortemp != 0:
            return None
        if self._light.state.get_rgb() is None:
            return

        rgb = self._light.state.get_rgb()
        if rgb[0] is None:
            # this is the case if the temperature was changed
            # do nothing until the RGB color was changed
            return
        warmwhite = self._light.state.get_warm_white()
        if warmwhite is None:
            return
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
