"""
Support for Plum Lightpad switches.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light.plum_lightpad
"""
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.light import (
    PLATFORM_SCHEMA, ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light)

REQUIREMENTS = ['plumlightpad==0.0.5']

CONF_USER = 'username'
CONF_PASSWORD = 'password'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_USER, default=None): cv.string,
    vol.Optional(CONF_PASSWORD, default=None): cv.string,
})


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup the demo light platform."""
    from plumlightpad import Plum

    if (config.get(CONF_USER) is not None and
            config.get(CONF_PASSWORD) is not None):
        plum = Plum(config.get(CONF_USER), config.get(CONF_PASSWORD))
        for key, value in plum.get_logical_loads().items():
            add_devices_callback([
                LogicalLoad(plum, key, value)
            ])


class LogicalLoad(Light):
    """Represenation of a demo light."""

    def __init__(
            self, plum, llid, load):
        """Initialize the light."""
        self._plum = plum
        self._llid = llid
        self._name = load['name']

        metrics = plum.get_metrics(self._llid)

        self._brightness = metrics['level']
        self._state = self._brightness > 0

        # sign up for events from all of the LightPads.
        for lpid in load['lightpads']:
            plum.register_event_listener(lpid, self.__process_event)

    def __process_event(self, event):
        if event['type'] == 'dimmerchange':
            self._brightness = event['level']
            self._state = self._brightness != 0
            self.schedule_update_ha_state()

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the light if any."""
        return self._name

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._state

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    def turn_on(self, **kwargs):
        """Turn the light on."""
        self._state = True

        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
            self._plum.set_level(self._llid, self._brightness)
        else:
            self._plum.turn_on(self._llid)

        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the light off."""
        self._state = False
        self._plum.turn_off(self._llid)
        self.schedule_update_ha_state()
