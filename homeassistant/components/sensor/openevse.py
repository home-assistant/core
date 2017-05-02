"""
Support for monitoring an OpenEVSE Charger.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.openevse/
"""
import logging

from requests import RequestException

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import TEMP_CELSIUS, CONF_HOST
from homeassistant.const import CONF_MONITORED_VARIABLES
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['openevsewifi==0.4']
SENSOR_TYPES = {
    'status': ['Charging Status', None],
    'charge_time': ['Charge Time Elapsed', 'minutes'],
    'ambient_temp': ['Ambient Termperature', TEMP_CELSIUS],
    'ir_temp': ['IR Temperature', TEMP_CELSIUS],
    'rtc_temp': ['RTC Temperature', TEMP_CELSIUS],
    'usage_session': ['Usage this Session', 'kWh'],
    'usage_total': ['Total Usage', 'kWh']
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_MONITORED_VARIABLES, default=['status']):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the OpenEVSE sensor."""
    import openevsewifi

    host = config.get(CONF_HOST)
    monitored_variables = config.get(CONF_MONITORED_VARIABLES)

    charger = openevsewifi.Charger(host)

    dev = []
    for variable in monitored_variables:
        dev.append(OpenEVSESensor(variable, charger))

    add_devices(dev)


class OpenEVSESensor(Entity):
    """Implementation of an OpenEVSE sensor."""

    # pylint: disable=too-many-arguments
    def __init__(self, sensor_type, charger):
        """Initialize the sensor."""
        self._name = SENSOR_TYPES[sensor_type][0]
        self.type = sensor_type
        self._state = None
        self.charger = charger
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this sensor."""
        return self._unit_of_measurement

    def update(self):
        """Get the monitored data from the charger."""
        try:
            if self.type == 'status':
                self._state = self.charger.getStatus()
            elif self.type == 'charge_time':
                self._state = self.charger.getChargeTimeElapsed() / 60
            elif self.type == 'ambient_temp':
                self._state = self.charger.getAmbientTemperature()
            elif self.type == 'ir_temp':
                self._state = self.charger.getIRTemperature()
            elif self.type == 'rtc_temp':
                self._state = self.charger.getRTCTemperature()
            elif self.type == 'usage_session':
                self._state = float(self.charger.getUsageSession()) / 1000
            elif self.type == 'usage_total':
                self._state = float(self.charger.getUsageTotal()) / 1000
            else:
                self._state = 'Unknown'
        except (RequestException, ValueError, KeyError):
            _LOGGER.warning("Could not update status for %s", self.name)
