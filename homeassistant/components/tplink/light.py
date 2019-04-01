"""
Support for TPLink lights.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light.tplink/
"""
import logging
import time

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_HS_COLOR, SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR, SUPPORT_COLOR_TEMP, Light)
import homeassistant.helpers.device_registry as dr
from homeassistant.util.color import (
    color_temperature_kelvin_to_mired as kelvin_to_mired,
    color_temperature_mired_to_kelvin as mired_to_kelvin)

from . import CONF_LIGHT, DOMAIN as TPLINK_DOMAIN

DEPENDENCIES = ['tplink']

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)

ATTR_CURRENT_POWER_W = 'current_power_w'
ATTR_DAILY_ENERGY_KWH = 'daily_energy_kwh'
ATTR_MONTHLY_ENERGY_KWH = 'monthly_energy_kwh'


def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the platform.

    Deprecated.
    """
    _LOGGER.warning('Loading as a platform is no longer supported, '
                    'convert to use the tplink component.')


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up discovered switches."""
    devs = []
    for dev in hass.data[TPLINK_DOMAIN][CONF_LIGHT]:
        devs.append(TPLinkSmartBulb(dev))

    async_add_entities(devs, True)

    return True


def brightness_to_percentage(byt):
    """Convert brightness from absolute 0..255 to percentage."""
    return int((byt*100.0)/255.0)


def brightness_from_percentage(percent):
    """Convert percentage to absolute value 0..255."""
    return (percent*255.0)/100.0


class TPLinkSmartBulb(Light):
    """Representation of a TPLink Smart Bulb."""

    def __init__(self, smartbulb) -> None:
        """Initialize the bulb."""
        self.smartbulb = smartbulb
        self._sysinfo = None
        self._state = None
        self._available = False
        self._color_temp = None
        self._brightness = None
        self._hs = None
        self._supported_features = None
        self._min_mireds = None
        self._max_mireds = None
        self._emeter_params = {}

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._sysinfo["mac"]

    @property
    def name(self):
        """Return the name of the Smart Bulb."""
        return self._sysinfo["alias"]

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "name": self.name,
            "model": self._sysinfo["model"],
            "manufacturer": 'TP-Link',
            "connections": {
                (dr.CONNECTION_NETWORK_MAC, self._sysinfo["mac"])
            },
            "sw_version": self._sysinfo["sw_ver"],
        }

    @property
    def available(self) -> bool:
        """Return if bulb is available."""
        return self._available

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._emeter_params

    def turn_on(self, **kwargs):
        """Turn the light on."""
        from pyHS100 import SmartBulb
        self.smartbulb.state = SmartBulb.BULB_STATE_ON

        if ATTR_COLOR_TEMP in kwargs:
            self.smartbulb.color_temp = \
                mired_to_kelvin(kwargs[ATTR_COLOR_TEMP])

        brightness = brightness_to_percentage(
            kwargs.get(ATTR_BRIGHTNESS, self.brightness or 255))
        if ATTR_HS_COLOR in kwargs:
            hue, sat = kwargs.get(ATTR_HS_COLOR)
            hsv = (int(hue), int(sat), brightness)
            self.smartbulb.hsv = hsv
        elif ATTR_BRIGHTNESS in kwargs:
            self.smartbulb.brightness = brightness

    def turn_off(self, **kwargs):
        """Turn the light off."""
        from pyHS100 import SmartBulb
        self.smartbulb.state = SmartBulb.BULB_STATE_OFF

    @property
    def min_mireds(self):
        """Return minimum supported color temperature."""
        return self._min_mireds

    @property
    def max_mireds(self):
        """Return maximum supported color temperature."""
        return self._max_mireds

    @property
    def color_temp(self):
        """Return the color temperature of this light in mireds for HA."""
        return self._color_temp

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def hs_color(self):
        """Return the color."""
        return self._hs

    @property
    def is_on(self):
        """Return True if device is on."""
        return self._state

    def update(self):
        """Update the TP-Link Bulb's state."""
        from pyHS100 import SmartDeviceException, SmartBulb
        try:
            if self._supported_features is None:
                self.get_features()

            self._state = (
                self.smartbulb.state == SmartBulb.BULB_STATE_ON)

            if self._supported_features & SUPPORT_BRIGHTNESS:
                self._brightness = brightness_from_percentage(
                    self.smartbulb.brightness)

            if self._supported_features & SUPPORT_COLOR_TEMP:
                if (self.smartbulb.color_temp is not None and
                        self.smartbulb.color_temp != 0):
                    self._color_temp = kelvin_to_mired(
                        self.smartbulb.color_temp)

            if self._supported_features & SUPPORT_COLOR:
                hue, sat, _ = self.smartbulb.hsv
                self._hs = (hue, sat)

            if self.smartbulb.has_emeter:
                self._emeter_params[ATTR_CURRENT_POWER_W] = '{:.1f}'.format(
                    self.smartbulb.current_consumption())
                daily_statistics = self.smartbulb.get_emeter_daily()
                monthly_statistics = self.smartbulb.get_emeter_monthly()
                try:
                    self._emeter_params[ATTR_DAILY_ENERGY_KWH] \
                        = "{:.3f}".format(
                            daily_statistics[int(time.strftime("%d"))])
                    self._emeter_params[ATTR_MONTHLY_ENERGY_KWH] \
                        = "{:.3f}".format(
                            monthly_statistics[int(time.strftime("%m"))])
                except KeyError:
                    # device returned no daily/monthly history
                    pass

            self._available = True

        except (SmartDeviceException, OSError) as ex:
            if self._available:
                _LOGGER.warning("Could not read state for %s: %s",
                                self.smartbulb.host, ex)
            self._available = False

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    def get_features(self):
        """Determine all supported features in one go."""
        self._sysinfo = self.smartbulb.sys_info
        self._supported_features = 0

        if self.smartbulb.is_dimmable:
            self._supported_features += SUPPORT_BRIGHTNESS
        if getattr(self.smartbulb, 'is_variable_color_temp', False):
            self._supported_features += SUPPORT_COLOR_TEMP
            self._min_mireds = kelvin_to_mired(
                self.smartbulb.valid_temperature_range[1])
            self._max_mireds = kelvin_to_mired(
                self.smartbulb.valid_temperature_range[0])
        if getattr(self.smartbulb, 'is_color', False):
            self._supported_features += SUPPORT_COLOR
