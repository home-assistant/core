"""Light platform support for Terncy."""
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_FLASH,
    LightEntity,
)

from .const import DOMAIN, TERNCY_MANU_NAME

_LOGGER = logging.getLogger(__name__)

SUPPORT_TERNCY_ON_OFF = SUPPORT_FLASH
SUPPORT_TERNCY_DIMMABLE = SUPPORT_TERNCY_ON_OFF | SUPPORT_BRIGHTNESS
SUPPORT_TERNCY_CT = SUPPORT_TERNCY_DIMMABLE | SUPPORT_COLOR_TEMP
SUPPORT_TERNCY_COLOR = SUPPORT_TERNCY_DIMMABLE | SUPPORT_COLOR
SUPPORT_TERNCY_EXTENDED = SUPPORT_TERNCY_DIMMABLE | SUPPORT_COLOR | SUPPORT_COLOR_TEMP


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Old way of setting up Terncy lights.

    Can only be called when a user accidentally mentions Terncy platform in their
    config. But even in that case it would have been ignored.
    """
    _LOGGER.debug(" terncy light async_setup_platform")


def get_attr_value(attrs, key):
    """Read attr value from terncy attributes."""
    for a in attrs:
        if "attr" in a and a["attr"] == key:
            return a["value"]
    return None


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Terncy lights from a config entry."""
    _LOGGER.debug("setup terncy light platorm")


class TerncyLight(LightEntity):
    """Representation of a Terncy light."""

    def __init__(self, api, devid, name, model, version, features):
        """Initialize the light."""
        self._device_id = devid
        self.hub_id = api.dev_id
        self._name = name
        self.model = model
        self.version = version
        self.api = api
        self._available = False
        self._features = features
        self._onoff = False
        self._ct = 0
        self._hs = (0, 0)
        self._bri = 0

    def update_state(self, attrs):
        """Updateterncy state."""
        _LOGGER.debug("update state event to")
        _LOGGER.debug(attrs)
        on = get_attr_value(attrs, "on")
        if on is not None:
            self._onoff = on == 1
        bri = get_attr_value(attrs, "brightness")
        if bri:
            self._bri = int(bri / 100 * 255)
        ct = get_attr_value(attrs, "colorTemperature")
        if ct:
            self._ct = ct
        hue = get_attr_value(attrs, "hue")
        sat = get_attr_value(attrs, "saturation")
        if hue is not None:
            hue = hue / 255 * 360.0
            self._hs = (hue, self._hs[1])
        if sat is not None:
            sat = sat / 255 * 100
            self._hs = (self._hs[0], sat)
        self.schedule_update_ha_state()

    @property
    def unique_id(self):
        """Return terncy unique id."""
        return self._device_id

    @property
    def device_id(self):
        """Return terncy device id."""
        return self._device_id

    @property
    def name(self):
        """Return terncy device name."""
        return self._name

    @property
    def brightness(self):
        """Return terncy device brightness."""
        return self._bri

    @property
    def hs_color(self):
        """Return terncy device color."""
        return self._hs

    @property
    def color_temp(self):
        """Return terncy device color temperature."""
        return self._ct

    @property
    def min_mireds(self):
        """Return terncy device min mireds."""
        return 50

    @property
    def max_mireds(self):
        """Return terncy device max mireds."""
        return 400

    @property
    def is_on(self):
        """Return if terncy device is on."""
        return self._onoff

    @property
    def available(self):
        """Return if terncy device is available."""
        return self._available

    @property
    def supported_features(self):
        """Return the terncy device feature."""
        return self._features

    @property
    def device_info(self):
        """Return the terncy device info."""
        return {
            "identifiers": {(DOMAIN, self.device_id)},
            "name": self.name,
            "manufacturer": TERNCY_MANU_NAME,
            "model": self.model,
            "sw_version": self.version,
            "via_device": (DOMAIN, self.hub_id),
        }

    async def async_turn_on(self, **kwargs):
        """Turn on terncy light."""
        _LOGGER.debug("turn on")
        _LOGGER.debug(kwargs)
        await self.api.set_onoff(self._device_id, 1)
        self._onoff = True
        if ATTR_BRIGHTNESS in kwargs:
            bri = kwargs.get(ATTR_BRIGHTNESS)
            terncy_bri = int(bri / 255 * 100)
            await self.api.set_attribute(self._device_id, "brightness", terncy_bri, 0)
            self._bri = bri
        if ATTR_COLOR_TEMP in kwargs:
            ct = kwargs.get(ATTR_COLOR_TEMP)
            if ct < 50:
                ct = 50
            if ct > 400:
                ct = 400
            await self.api.set_attribute(self._device_id, "colorTemperature", ct, 0)
            self._ct = ct
        if ATTR_HS_COLOR in kwargs:
            hs = kwargs.get(ATTR_HS_COLOR)
            terncy_hue = int(hs[0] / 360 * 255)
            terncy_sat = int(hs[1] / 100 * 255)
            await self.api.set_attribute(self._device_id, "hue", terncy_hue, 0)
            await self.api.set_attribute(self._device_id, "sat", terncy_sat, 0)
            self._hs = hs
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn off terncy light."""
        _LOGGER.debug("turn off")
        self._onoff = False
        await self.api.set_onoff(self._device_id, 0)
        self.async_write_ha_state()

    @property
    def device_state_attributes(self):
        """Get terncy light states."""
        return {}
