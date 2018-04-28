"""
Support for Nest Thermostat Sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.nest/
"""
from itertools import chain
import logging

from homeassistant.components.nest import DATA_NEST
from homeassistant.helpers.entity import Entity
from homeassistant.const import (TEMP_CELSIUS, TEMP_FAHRENHEIT,
                                 CONF_MONITORED_CONDITIONS)

DEPENDENCIES = ['nest']
SENSOR_TYPES = ['humidity',
                'operation_mode',
                'hvac_state']

SENSOR_TYPES_DEPRECATED = ['last_ip',
                           'local_ip',
                           'last_connection']

DEPRECATED_WEATHER_VARS = {'weather_humidity': 'humidity',
                           'weather_temperature': 'temperature',
                           'weather_condition': 'condition',
                           'wind_speed': 'kph',
                           'wind_direction': 'direction'}

SENSOR_UNITS = {'humidity': '%', 'temperature': '°C'}

PROTECT_VARS = ['co_status', 'smoke_status', 'battery_health']

PROTECT_VARS_DEPRECATED = ['battery_level']

SENSOR_TEMP_TYPES = ['temperature', 'target']

_SENSOR_TYPES_DEPRECATED = SENSOR_TYPES_DEPRECATED \
    + list(DEPRECATED_WEATHER_VARS.keys()) + PROTECT_VARS_DEPRECATED

_VALID_SENSOR_TYPES = SENSOR_TYPES + SENSOR_TEMP_TYPES + PROTECT_VARS

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Nest Sensor."""
    if discovery_info is None:
        return

    nest = hass.data[DATA_NEST]

    # Add all available sensors if no Nest sensor config is set
    if discovery_info == {}:
        conditions = _VALID_SENSOR_TYPES
    else:
        conditions = discovery_info.get(CONF_MONITORED_CONDITIONS, {})

    for variable in conditions:
        if variable in _SENSOR_TYPES_DEPRECATED:
            if variable in DEPRECATED_WEATHER_VARS:
                wstr = ("Nest no longer provides weather data like %s. See "
                        "https://home-assistant.io/components/#weather "
                        "for a list of other weather components to use." %
                        variable)
            else:
                wstr = (variable + " is no a longer supported "
                        "monitored_conditions. See "
                        "https://home-assistant.io/components/"
                        "binary_sensor.nest/ for valid options.")

            _LOGGER.error(wstr)

    all_sensors = []
    for structure, device in chain(nest.thermostats(), nest.smoke_co_alarms()):
        sensors = [NestBasicSensor(structure, device, variable)
                   for variable in conditions
                   if variable in SENSOR_TYPES and device.is_thermostat]
        sensors += [NestTempSensor(structure, device, variable)
                    for variable in conditions
                    if variable in SENSOR_TEMP_TYPES and device.is_thermostat]
        sensors += [NestProtectSensor(structure, device, variable)
                    for variable in conditions
                    if variable in PROTECT_VARS and device.is_smoke_co_alarm]
        all_sensors.extend(sensors)

    add_devices(all_sensors, True)


class NestSensor(Entity):
    """Representation of a Nest sensor."""

    def __init__(self, structure, device, variable):
        """Initialize the sensor."""
        self.structure = structure
        self.device = device
        self.variable = variable

        # device specific
        self._location = self.device.where
        self._name = "{} {}".format(self.device.name_long,
                                    self.variable.replace("_", " "))
        self._state = None
        self._unit = None

    @property
    def name(self):
        """Return the name of the nest, if any."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit


class NestBasicSensor(NestSensor):
    """Representation a basic Nest sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Retrieve latest state."""
        self._unit = SENSOR_UNITS.get(self.variable, None)

        if self.variable == 'operation_mode':
            self._state = getattr(self.device, "mode")
        else:
            self._state = getattr(self.device, self.variable)


class NestTempSensor(NestSensor):
    """Representation of a Nest Temperature sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return 'temperature'

    def update(self):
        """Retrieve latest state."""
        if self.device.temperature_scale == 'C':
            self._unit = TEMP_CELSIUS
        else:
            self._unit = TEMP_FAHRENHEIT

        temp = getattr(self.device, self.variable)
        if temp is None:
            self._state = None

        if isinstance(temp, tuple):
            low, high = temp
            self._state = "%s-%s" % (int(low), int(high))
        else:
            self._state = round(temp, 1)


class NestProtectSensor(NestSensor):
    """Return the state of nest protect."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Retrieve latest state."""
        self._state = getattr(self.device, self.variable).capitalize()
