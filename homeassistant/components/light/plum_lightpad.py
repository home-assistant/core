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


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup the Plum Lightpad Light."""
    plum = hass.data['plum']
    for llid, load in plum.get_logical_loads().items():
        print(load)
        add_devices_callback([
            LightpadLogicalLoad(plum, llid, load)
        ])


class LightpadLogicalLoad(Light):
    """Represenation of a Plum Lightpad dimmer."""

    def __init__(self, plum, llid, load):
        """Initialize the light."""
        self._plum = plum
        self._llid = llid
        self._name = load['name']

        metrics = plum.get_logical_load_metrics(self._llid)

        print(metrics)

        self._brightness = metrics['level']

        # sign up for events from the lightpad.
        for lpid, lightpad in load['lightpads'].items():
            plum.register_event_listener(lpid, self.__process_event)

    def __process_event(self, event):
        print(event)
        if event['type'] == 'dimmerchange':
            self._brightness = event['level']
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
            self._plum.set_logical_load_level(self._llid, self._brightness)
        else:
            self._plum.turn_logical_load_on(self._llid)

    def turn_off(self, **kwargs):
        """Turn the light off."""
        self._plum.turn_logical_load_off(self._llid)
