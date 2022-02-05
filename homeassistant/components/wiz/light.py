"""WiZ integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from pywizlight import PilotBuilder, wizlight
from pywizlight.bulblibrary import BulbClass, BulbType
from pywizlight.exceptions import WizLightNotKnownBulb, WizLightTimeOutError
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
import homeassistant.util.color as color_utils

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SUPPORT_FEATURES_RGB = (
    SUPPORT_BRIGHTNESS | SUPPORT_COLOR | SUPPORT_COLOR_TEMP | SUPPORT_EFFECT
)


# set poll interval to 15 sec because of changes from external to the bulb
SCAN_INTERVAL = timedelta(seconds=15)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the WiZ Platform from config_flow."""
    # Assign configuration variables.
    wiz_data = hass.data[DOMAIN][entry.entry_id]
    wizbulb = WizBulbEntity(wiz_data.bulb, entry.data.get(CONF_NAME), wiz_data.scenes)
    # Add devices with defined name
    async_add_entities([wizbulb], update_before_add=True)
    return True


class WizBulbEntity(LightEntity):
    """Representation of WiZ Light bulb."""

    def __init__(self, light: wizlight, name, scenes):
        """Initialize an WiZLight."""
        self._light = light
        self._state = None
        self._brightness = None
        self._attr_name = name
        self._rgb_color = None
        self._temperature = None
        self._hscolor = None
        self._available = None
        self._effect = None
        self._scenes: list[str] = scenes
        self._bulbtype: BulbType = light.bulbtype
        self._mac = light.mac
        self._attr_unique_id = light.mac
        # new init states
        self._attr_min_mireds = self.get_min_mireds()
        self._attr_max_mireds = self.get_max_mireds()
        self._attr_supported_features = self.get_supported_features()

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def rgb_color(self):
        """Return the color property."""
        return self._rgb_color

    @property
    def hs_color(self):
        """Return the hs color value."""
        return self._hscolor

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._state

    async def async_turn_on(self, **kwargs):
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

    async def async_turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        await self._light.turn_off()

    @property
    def color_temp(self):
        """Return the CT color value in mireds."""
        return self._temperature

    def get_min_mireds(self) -> int:
        """Return the coldest color_temp that this light supports."""
        if self._bulbtype is None:
            return color_utils.color_temperature_kelvin_to_mired(6500)
        # DW bulbs have no kelvin
        if self._bulbtype.bulb_type == BulbClass.DW:
            return 0
        # If bulbtype is TW or RGB then return the kelvin value
        try:
            return color_utils.color_temperature_kelvin_to_mired(
                self._bulbtype.kelvin_range.max
            )
        except WizLightNotKnownBulb:
            _LOGGER.debug("Kelvin is not present in the library. Fallback to 6500")
            return color_utils.color_temperature_kelvin_to_mired(6500)

    def get_max_mireds(self) -> int:
        """Return the warmest color_temp that this light supports."""
        if self._bulbtype is None:
            return color_utils.color_temperature_kelvin_to_mired(2200)
        # DW bulbs have no kelvin
        if self._bulbtype.bulb_type == BulbClass.DW:
            return 0
        # If bulbtype is TW or RGB then return the kelvin value
        try:
            return color_utils.color_temperature_kelvin_to_mired(
                self._bulbtype.kelvin_range.min
            )
        except WizLightNotKnownBulb:
            _LOGGER.debug("Kelvin is not present in the library. Fallback to 2200")
            return color_utils.color_temperature_kelvin_to_mired(2200)

    def get_supported_features(self) -> int:
        """Flag supported features."""
        if not self._bulbtype:
            # fallback
            return SUPPORT_FEATURES_RGB
        features = 0
        try:
            # Map features for better reading
            if self._bulbtype.features.brightness:
                features = features | SUPPORT_BRIGHTNESS
            if self._bulbtype.features.color:
                features = features | SUPPORT_COLOR
            if self._bulbtype.features.effect:
                features = features | SUPPORT_EFFECT
            if self._bulbtype.features.color_tmp:
                features = features | SUPPORT_COLOR_TEMP
            return features
        except WizLightNotKnownBulb:
            _LOGGER.warning(
                "Bulb is not present in the library. Fallback to full feature"
            )
            return SUPPORT_FEATURES_RGB

    @property
    def effect(self):
        """Return the current effect."""
        return self._effect

    @property
    def effect_list(self):
        """Return the list of supported effects.

        URL: https://docs.pro.wizconnected.com/#light-modes
        """
        return self._scenes

    @property
    def available(self):
        """Return if light is available."""
        return self._available

    async def async_update(self):
        """Fetch new state data for this light."""
        await self.update_state()

        if self._state is not None and self._state is not False:
            self.update_brightness()
            self.update_temperature()
            self.update_color()
            self.update_effect()

    @property
    def device_info(self):
        """Get device specific attributes."""
        return {
            "connections": {(CONNECTION_NETWORK_MAC, self._mac)},
            "name": self._attr_name,
            "manufacturer": "WiZ Light Platform",
            "model": self._bulbtype.name,
        }

    def update_state_available(self):
        """Update the state if bulb is available."""
        self._state = self._light.status
        self._available = True

    def update_state_unavailable(self):
        """Update the state if bulb is unavailable."""
        self._state = False
        self._available = False

    async def update_state(self):
        """Update the state."""
        try:
            await self._light.updateState()
        except (ConnectionRefusedError, TimeoutError, WizLightTimeOutError) as ex:
            _LOGGER.debug(ex)
            self.update_state_unavailable()
        else:
            if self._light.state is None:
                self.update_state_unavailable()
            else:
                self.update_state_available()
        _LOGGER.debug(
            "[wizlight %s] updated state: %s and available: %s",
            self._light.ip,
            self._state,
            self._available,
        )

    def update_brightness(self):
        """Update the brightness."""
        if self._light.state.get_brightness() is None:
            return
        brightness = self._light.state.get_brightness()
        if 0 <= int(brightness) <= 255:
            self._brightness = int(brightness)
        else:
            _LOGGER.error(
                "Received invalid brightness : %s. Expected: 0-255", brightness
            )
            self._brightness = None

    def update_temperature(self):
        """Update the temperature."""
        colortemp = self._light.state.get_colortemp()
        if colortemp is None or colortemp == 0:
            self._temperature = None
            return

        _LOGGER.debug(
            "[wizlight %s] kelvin from the bulb: %s", self._light.ip, colortemp
        )
        temperature = color_utils.color_temperature_kelvin_to_mired(colortemp)
        self._temperature = temperature

    def update_color(self):
        """Update the hs color."""
        colortemp = self._light.state.get_colortemp()
        if colortemp is not None and colortemp != 0:
            self._hscolor = None
            return
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
        self._hscolor = convertHSfromRGBCW(rgb, warmwhite)

    def update_effect(self):
        """Update the bulb scene."""
        self._effect = self._light.state.get_scene()

    async def get_bulb_type(self):
        """Get the bulb type."""
        if self._bulbtype is not None:
            return self._bulbtype
        try:
            self._bulbtype = await self._light.get_bulbtype()
            _LOGGER.info(
                "[wizlight %s] Initiate the WiZ bulb as %s",
                self._light.ip,
                self._bulbtype.name,
            )
        except WizLightTimeOutError:
            _LOGGER.debug(
                "[wizlight %s] Bulbtype update failed - Timeout", self._light.ip
            )
