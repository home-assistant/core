"""Support for Nanoleaf Lights."""
import logging

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_EFFECT, ATTR_HS_COLOR,
    ATTR_TRANSITION, PLATFORM_SCHEMA, SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR, SUPPORT_COLOR_TEMP, SUPPORT_EFFECT,
    SUPPORT_TRANSITION, Light)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TOKEN
import homeassistant.helpers.config_validation as cv
from homeassistant.util import color as color_util
from homeassistant.util.color import \
    color_temperature_mired_to_kelvin as mired_to_kelvin
from homeassistant.util.json import load_json, save_json

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Nanoleaf'

DATA_NANOLEAF = 'nanoleaf'

CONFIG_FILE = '.nanoleaf.conf'

ICON = 'mdi:triangle-outline'

SUPPORT_NANOLEAF = (SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP | SUPPORT_EFFECT |
                    SUPPORT_COLOR | SUPPORT_TRANSITION)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_TOKEN): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Nanoleaf light."""
    from pynanoleaf import Nanoleaf, Unavailable
    if DATA_NANOLEAF not in hass.data:
        hass.data[DATA_NANOLEAF] = dict()

    token = ''
    if discovery_info is not None:
        host = discovery_info['host']
        name = discovery_info['hostname']
        # if device already exists via config, skip discovery setup
        if host in hass.data[DATA_NANOLEAF]:
            return
        _LOGGER.info("Discovered a new Nanoleaf: %s", discovery_info)
        conf = load_json(hass.config.path(CONFIG_FILE))
        if conf.get(host, {}).get('token'):
            token = conf[host]['token']
    else:
        host = config[CONF_HOST]
        name = config[CONF_NAME]
        token = config[CONF_TOKEN]

    nanoleaf_light = Nanoleaf(host)

    if not token:
        token = nanoleaf_light.request_token()
        if not token:
            _LOGGER.error("Could not generate the auth token, did you press "
                          "and hold the power button on %s"
                          "for 5-7 seconds?", name)
            return
        conf = load_json(hass.config.path(CONFIG_FILE))
        conf[host] = {'token': token}
        save_json(hass.config.path(CONFIG_FILE), conf)

    nanoleaf_light.token = token

    try:
        nanoleaf_light.available
    except Unavailable:
        _LOGGER.error(
            "Could not connect to Nanoleaf Light: %s on %s", name, host)
        return

    hass.data[DATA_NANOLEAF][host] = nanoleaf_light
    add_entities([NanoleafLight(nanoleaf_light, name)], True)


class NanoleafLight(Light):
    """Representation of a Nanoleaf Light."""

    def __init__(self, light, name):
        """Initialize an Nanoleaf light."""
        self._available = True
        self._brightness = None
        self._color_temp = None
        self._effect = None
        self._effects_list = None
        self._light = light
        self._name = name
        self._hs_color = None
        self._state = None

    @property
    def available(self):
        """Return availability."""
        return self._available

    @property
    def brightness(self):
        """Return the brightness of the light."""
        if self._brightness is not None:
            return int(self._brightness * 2.55)
        return None

    @property
    def color_temp(self):
        """Return the current color temperature."""
        if self._color_temp is not None:
            return color_util.color_temperature_kelvin_to_mired(
                self._color_temp)
        return None

    @property
    def effect(self):
        """Return the current effect."""
        return self._effect

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return self._effects_list

    @property
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        return 154

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        return 833

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._state

    @property
    def hs_color(self):
        """Return the color in HS."""
        return self._hs_color

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_NANOLEAF

    def turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        hs_color = kwargs.get(ATTR_HS_COLOR)
        color_temp_mired = kwargs.get(ATTR_COLOR_TEMP)
        effect = kwargs.get(ATTR_EFFECT)
        transition = kwargs.get(ATTR_TRANSITION)

        if hs_color:
            hue, saturation = hs_color
            self._light.hue = int(hue)
            self._light.saturation = int(saturation)
        if color_temp_mired:
            self._light.color_temperature = mired_to_kelvin(color_temp_mired)

        if transition:
            if brightness:  # tune to the required brightness in n seconds
                self._light.brightness_transition(
                    int(brightness / 2.55), int(transition))
            else:  # If brightness is not specified, assume full brightness
                self._light.brightness_transition(100, int(transition))
        else:  # If no transition is occurring, turn on the light
            self._light.on = True
            if brightness:
                self._light.brightness = int(brightness / 2.55)

        if effect:
            self._light.effect = effect

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        transition = kwargs.get(ATTR_TRANSITION)
        if transition:
            self._light.brightness_transition(0, int(transition))
        else:
            self._light.on = False

    def update(self):
        """Fetch new state data for this light."""
        from pynanoleaf import Unavailable
        try:
            self._available = self._light.available
            self._brightness = self._light.brightness
            self._color_temp = self._light.color_temperature
            self._effect = self._light.effect
            self._effects_list = self._light.effects
            self._hs_color = self._light.hue, self._light.saturation
            self._state = self._light.on
        except Unavailable as err:
            _LOGGER.error("Could not update status for %s (%s)",
                          self.name, err)
            self._available = False
