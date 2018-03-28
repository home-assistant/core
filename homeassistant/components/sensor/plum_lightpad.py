"""
Support for Plum Lightpad switches.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light.plum_lightpad
"""
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.light import PLATFORM_SCHEMA
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['plum_lightpad']
WATTS = 'Watts'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    plum = hass.data['plum']

    for lpid, lightpad in plum.get_lightpads().items():
        print(lightpad)
        add_devices_callback([
            LightpadPowerMeter(plum, lpid, lightpad)
        ])

class LightpadPowerMeter(Entity):
    """Representation of a Lightpad power meter Sensor."""

    def __init__(self, plum, lpid, lightpad):
        self._plum = plum
        self._lpid = lpid
        self._name = lightpad['name']

        metrics = plum.get_lightpad_metrics(self._lpid)

        self._power = metrics['power']

        plum.register_event_listener(lpid, self.__process_event)

    def __process_event(self, event):
        print(event)
        if event['type'] == 'power':
            self._power = event['watts']
            self.schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._power

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return WATTS
