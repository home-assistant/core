"""
Support for getting the state of a Thermoworks Smoke Thermometer.

Requires Smoke Gateway Wifi with an internet connection.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.thermoworks_smoke/
"""
import logging

from requests import RequestException
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import TEMP_FAHRENHEIT, CONF_EMAIL, CONF_PASSWORD,\
    CONF_MONITORED_VARIABLES, CONF_EXCLUDE
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['thermoworks_smoke==0.1.5']

_LOGGER = logging.getLogger(__name__)

PROBE_1 = 'probe1'
PROBE_2 = 'probe2'
PROBE_1_MIN = 'probe1Min'
PROBE_1_MAX = 'probe1Max'
PROBE_2_MIN = 'probe2Min'
PROBE_2_MAX = 'probe2Max'

SENSOR_TYPES = {
    PROBE_1: 'Probe 1',
    PROBE_2: 'Probe 2',
    PROBE_1_MIN: 'Probe 1 Min',
    PROBE_1_MAX: 'Probe 1 Max',
    PROBE_2_MIN: 'Probe 2 Min',
    PROBE_2_MAX: 'Probe 2 Max',
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_EMAIL): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_MONITORED_VARIABLES, default=[PROBE_1, PROBE_2]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_EXCLUDE, default=[]):
        vol.All(cv.ensure_list),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the thermoworks sensor."""
    import thermoworks_smoke

    email = config.get(CONF_EMAIL)
    password = config.get(CONF_PASSWORD)
    monitored_variables = config.get(CONF_MONITORED_VARIABLES)
    excluded = config.get(CONF_EXCLUDE)

    mgr = thermoworks_smoke.initialize_app(email, password, True, excluded)

    # list of sensor devices
    dev = []

    # get list of registered devices
    for serial in mgr.serials():
        for variable in monitored_variables:
            dev.append(ThermoworksSmokeSensor(variable, serial, mgr))

    add_devices(dev, True)


class ThermoworksSmokeSensor(Entity):
    """Implementation of a thermoworks smoke sensor."""

    def __init__(self, sensor_type, serial, mgr):
        """Initialize the sensor."""
        self._name = "{name} {sensor}".format(name=mgr.name(serial),
                                              sensor=SENSOR_TYPES[sensor_type])
        self.type = sensor_type
        self._state = None
        self._attributes = {}
        self._unit_of_measurement = TEMP_FAHRENHEIT
        self.serial = serial
        self.mgr = mgr
        self.update_unit()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this sensor."""
        return self._unit_of_measurement

    def update_unit(self):
        """Set the units from the data."""
        if PROBE_2 in self.type:
            self._unit_of_measurement = self.mgr.units(self.serial, PROBE_2)
        else:
            self._unit_of_measurement = self.mgr.units(self.serial, PROBE_1)

    def update(self):
        """Get the monitored data from firebase."""
        try:
            values = self.mgr.data(self.serial)

            # set state from data based on type of sensor
            self._state = values.get(self.type)

            # set units
            self.update_unit()

            # set basic attributes for all sensors
            self._attributes = {
                'serial': self.serial,
                'time': values['time'],
                'localtime': values['localtime'],
                'original_unit': self._unit_of_measurement
            }

            # set extended attributes for main probe sensors
            if self.type in [PROBE_1, PROBE_2]:
                for key, val in values.items():
                    # add all attributes that don't contain any probe name
                    # or contain a matching probe name
                    if (
                            (self.type == PROBE_1 and key.find(PROBE_2) == -1)
                            or
                            (self.type == PROBE_2 and key.find(PROBE_1) == -1)
                    ):
                        # strip probe label
                        key = key.replace(self.type, '')
                        # ensure first char is lowercase
                        key = key[:1].lower() + key[1:]
                        # add to attrs
                        if key:
                            self._attributes[key] = val

        except (RequestException, ValueError, KeyError):
            _LOGGER.warning("Could not update status for %s", self.name)
