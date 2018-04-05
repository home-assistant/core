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

    for llid, load in plum.logical_loads.items():
        print(load)
        add_devices_callback([
            PowerSensor(plum=plum, llid=llid, load=load)
        ])

class PowerSensor(Entity):
    """Representation of a Lightpad power meter Sensor."""

    def __init__(self, plum, llid, load):
        self._plum = plum
        self._llid = llid
        self._name = load.name

        plum.add_power_listener(self._llid, self.powerchanged)
        self._power = load.power

    def powerchanged(self, power):
        self._power = power
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
