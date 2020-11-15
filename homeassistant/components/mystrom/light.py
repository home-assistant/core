"""Support for myStrom Wifi bulbs."""
import logging

from pymystrom.bulb import MyStromBulb
from pymystrom.exceptions import MyStromConnectionError
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    PLATFORM_SCHEMA,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_EFFECT,
    SUPPORT_FLASH,
    LightEntity,
)
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "myStrom bulb"

SUPPORT_MYSTROM = SUPPORT_BRIGHTNESS | SUPPORT_EFFECT | SUPPORT_FLASH | SUPPORT_COLOR

EFFECT_RAINBOW = "rainbow"
EFFECT_SUNRISE = "sunrise"

MYSTROM_EFFECT_LIST = [EFFECT_RAINBOW, EFFECT_SUNRISE]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_MAC): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the myStrom light integration."""
    host = config.get(CONF_HOST)
    mac = config.get(CONF_MAC)
    name = config.get(CONF_NAME)

    bulb = MyStromBulb(host, mac)
    try:
        await bulb.get_state()
        if bulb.bulb_type != "rgblamp":
            _LOGGER.error("Device %s (%s) is not a myStrom bulb", host, mac)
            return
    except MyStromConnectionError as err:
        _LOGGER.warning("No route to myStrom bulb: %s", host)
        raise PlatformNotReady() from err

    async_add_entities([MyStromLight(bulb, name, mac)], True)


class MyStromLight(LightEntity):
    """Representation of the myStrom WiFi bulb."""

    def __init__(self, bulb, name, mac):
        """Initialize the light."""
        self._bulb = bulb
        self._name = name
        self._state = None
        self._available = False
        self._brightness = 0
        self._color_h = 0
        self._color_s = 0
        self._mac = mac

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._mac

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_MYSTROM

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def hs_color(self):
        """Return the color of the light."""
        return self._color_h, self._color_s

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return MYSTROM_EFFECT_LIST

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._state

    async def async_turn_on(self, **kwargs):
        """Turn on the light."""
        brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
        effect = kwargs.get(ATTR_EFFECT)

        if ATTR_HS_COLOR in kwargs:
            color_h, color_s = kwargs[ATTR_HS_COLOR]
        elif ATTR_BRIGHTNESS in kwargs:
            # Brightness update, keep color
            color_h, color_s = self._color_h, self._color_s
        else:
            color_h, color_s = 0, 0  # Back to white

        try:
            if not self.is_on:
                await self._bulb.set_on()
            if brightness is not None:
                await self._bulb.set_color_hsv(
                    int(color_h), int(color_s), round(brightness * 100 / 255)
                )
            if effect == EFFECT_SUNRISE:
                await self._bulb.set_sunrise(30)
            if effect == EFFECT_RAINBOW:
                await self._bulb.set_rainbow(30)
        except MyStromConnectionError:
            _LOGGER.warning("No route to myStrom bulb")

    async def async_turn_off(self, **kwargs):
        """Turn off the bulb."""
        try:
            await self._bulb.set_off()
        except MyStromConnectionError:
            _LOGGER.warning("myStrom bulb not online")

    async def async_update(self):
        """Fetch new state data for this light."""
        try:
            await self._bulb.get_state()
            self._state = self._bulb.state

            colors = self._bulb.color
            try:
                color_h, color_s, color_v = colors.split(";")
            except ValueError:
                color_s, color_v = colors.split(";")
                color_h = 0

            self._color_h = int(color_h)
            self._color_s = int(color_s)
            self._brightness = int(color_v) * 255 / 100

            self._available = True
        except MyStromConnectionError:
            _LOGGER.warning("No route to myStrom bulb")
            self._available = False
