"""
Support for Plum Lightpad switches.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light.plum_lightpad
"""
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.light import (
    PLATFORM_SCHEMA, ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light)
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD

DEPENDENCIES = ['plum_lightpad']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})


async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup the Plum Lightpad Light."""
    plum = hass.data['plum']

    for llid, load in plum.logical_loads.items():
        print(load)

        async_add_devices([
            LightpadLogicalLoad(plum, llid, load)
            # glow ring (color, forced, timeout, glowFade, Intensity, tracksDimmer)
        ])


class LightpadLogicalLoad(Light):
    """Represenation of a Plum Lightpad dimmer."""

    def __init__(self, plum, llid, load):
        """Initialize the light."""
        self._plum = plum
        self._llid = llid
        self._load = load
        self._name = load.name
        self._brightness = load.level

        plum.add_load_listener(self._llid, self.dimmerchange)

    def dimmerchange(self, level):
        self._brightness = level
        self.schedule_update_ha_state()

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
        return self._brightness > 0

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    def turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
            self._load.brightness(self._brightness)
        else:
            self._load.on()

    def turn_off(self, **kwargs):
        """Turn the light off."""
        self._load.off()


# class LightpadGlowRing(Light):
#     """Represenation of a Plum Lightpad dimmer glow ring."""
#
#     def __init__(self, plum, llid, load):
#         """Initialize the light."""
#         self._plum = plum
#         self._llid = llid
#         self._name = load['name']
