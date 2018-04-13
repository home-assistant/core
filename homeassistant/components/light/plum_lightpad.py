"""
Support for Plum Lightpad switches.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light.plum_lightpad
"""
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.light import (
    PLATFORM_SCHEMA, ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light, SUPPORT_COLOR, SUPPORT_WHITE_VALUE, ATTR_MIN_MIREDS,
    ATTR_MAX_MIREDS, SUPPORT_COLOR_TEMP, ATTR_RGB_COLOR, ATTR_HS_COLOR, PROP_TO_ATTR, ATTR_XY_COLOR, ATTR_WHITE_VALUE)
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
import homeassistant.util.color as color_util

DEPENDENCIES = ['plum_lightpad']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})


async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup the Plum Lightpad Light."""
    plum = hass.data['plum']

    def new_load(logical_load):
        async_add_devices([
            PlumLight(load=logical_load)
        ])

    for load in plum.loads.values():
        new_load(load)

    plum.add_load_listener(new_load)

    def new_lightpad(lightpad):
        async_add_devices([
            GlowRing(lightpad=lightpad)
        ])

    for lightpad in plum.lightpads.values():
        new_lightpad(lightpad)

    plum.add_lightpad_listener(new_lightpad)


class PlumLight(Light):
    """Represenation of a Plum Lightpad dimmer."""

    def __init__(self, load):
        """Initialize the light."""
        self._load = load
        self._brightness = load.level

        self._load.add_event_listener('dimmerchange', self.dimmerchange)

    def dimmerchange(self, event):
        self._brightness = event['level']
        self.schedule_update_ha_state()

    @property
    def llid(self):
        return self._load.llid

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the switch if any."""
        return self._load.name

    @property
    def brightness(self) -> int:
        """Return the brightness of this switch between 0..255."""
        return self._brightness

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._brightness > 0

    @property
    def dimmable(self):
        return self._load.dimmable

    @property
    def device_state_attributes(self):
        return {
            'llid': self.llid,
            'brightness': self.brightness,
            'dimmable': self.dimmable
        }

    @property
    def supported_features(self):
        """Flag supported features."""
        if self.dimmable:
            return SUPPORT_BRIGHTNESS
        else:
            return None

    def turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
            self._load.turn_on(self._brightness)
        else:
            self._load.turn_on()

    def turn_off(self, **kwargs):
        """Turn the light off."""
        self._load.turn_off()


class GlowRing(Light):
    """Represenation of a Plum Lightpad dimmer glow ring."""

    def __init__(self, lightpad):
        """Initialize the light."""
        self._lightpad = lightpad
        self._name = lightpad.friendly_name + " Glow Ring"
        self._red = lightpad.glow_color['red']
        self._green = lightpad.glow_color['green']
        self._blue = lightpad.glow_color['blue']
        self._white = lightpad.glow_color['white']
        self._brightness = lightpad.glow_intensity * 255.0
        lightpad.add_event_listener('configchange', self.configchange_event)

    def configchange_event(self, event):
        config = event['changes']
        self._red = config['glowColor']['red']
        self._green = config['glowColor']['green']
        self._blue = config['glowColor']['blue']
        self._white = config['glowColor']['white']
        self._brightness = config['glowIntensity'] * 255.0
        self.schedule_update_ha_state()

    @property
    def red(self):
        return self._red

    @property
    def green(self):
        return self._green

    @property
    def blue(self):
        return self._blue

    @property
    def white_value(self):
        return self._white

    @property
    def rgb_color(self):
        return self.red, self.green, self.blue

    @property
    def hs_color(self):
        """Return the hue and saturation color value [float, float]."""
        return color_util.color_RGB_to_hs(self.red, self.green, self.blue)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the switch if any."""
        return self._name

    @property
    def brightness(self) -> int:
        """Return the brightness of this switch between 0..255."""
        return self._brightness

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._lightpad.glow_enabled

    @property
    def icon(self):
        return 'mdi:crop-portrait'

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS | SUPPORT_COLOR

    @property
    def device_state_attributes(self):
        return {
            'red': self._red, 'green': self._green, 'blue': self._blue, 'white': self._white,
            'glowTimeout': self._lightpad.glow_timeout, 'glowFade': self._lightpad.glow_fade,
        }

    def turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]

            self._lightpad.set_config({"glowIntensity": self._brightness / 255.0})
        elif ATTR_HS_COLOR in kwargs:
            self._red, self._green, self._blue = color_util.color_hs_to_RGB(*kwargs[ATTR_HS_COLOR])
            self._lightpad.set_glow_color(self.red, self.green, self.blue, self.white_value)
        else:
            self._lightpad.set_config({"glowEnabled": True})

        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the light off."""
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
            self._lightpad.set_config({"glowIntensity": self._brightness})
        else:
            self._lightpad.set_config({"glowEnabled": False})
