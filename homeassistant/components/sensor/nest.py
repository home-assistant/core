"""
Support for Nest Thermostat Sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.nest/
"""
from itertools import chain

import voluptuous as vol

import homeassistant.components.nest as nest
from homeassistant.helpers.entity import Entity
from homeassistant.const import (
    TEMP_CELSIUS, CONF_PLATFORM, CONF_SCAN_INTERVAL, CONF_MONITORED_CONDITIONS
)

DEPENDENCIES = ['nest']
SENSOR_TYPES = ['humidity',
                'mode',
                'last_ip',
                'local_ip',
                'last_connection',
                'battery_level']

WEATHER_VARS = {'weather_humidity': 'humidity',
                'weather_temperature': 'temperature',
                'weather_condition': 'condition',
                'wind_speed': 'kph',
                'wind_direction': 'direction'}

SENSOR_UNITS = {'humidity': '%', 'battery_level': 'V',
                'kph': 'kph', 'temperature': '°C'}

PROTECT_VARS = ['co_status',
                'smoke_status',
                'battery_level']

SENSOR_TEMP_TYPES = ['temperature', 'target']

_VALID_SENSOR_TYPES = SENSOR_TYPES + SENSOR_TEMP_TYPES + PROTECT_VARS + \
                      list(WEATHER_VARS.keys())

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): nest.DOMAIN,
    vol.Optional(CONF_SCAN_INTERVAL):
        vol.All(vol.Coerce(int), vol.Range(min=1)),
    vol.Required(CONF_MONITORED_CONDITIONS): [vol.In(_VALID_SENSOR_TYPES)],
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Nest Sensor."""
    for structure, device in chain(nest.devices(), nest.protect_devices()):
        sensors = [NestBasicSensor(structure, device, variable)
                   for variable in config[CONF_MONITORED_CONDITIONS]
                   if variable in SENSOR_TYPES and is_thermostat(device)]
        sensors += [NestTempSensor(structure, device, variable)
                    for variable in config[CONF_MONITORED_CONDITIONS]
                    if variable in SENSOR_TEMP_TYPES and is_thermostat(device)]
        sensors += [NestWeatherSensor(structure, device,
                                      WEATHER_VARS[variable])
                    for variable in config[CONF_MONITORED_CONDITIONS]
                    if variable in WEATHER_VARS and is_thermostat(device)]
        sensors += [NestProtectSensor(structure, device, variable)
                    for variable in config[CONF_MONITORED_CONDITIONS]
                    if variable in PROTECT_VARS and is_protect(device)]

        add_devices(sensors)


def is_thermostat(device):
    """Target devices that are Nest Thermostats."""
    return bool(device.__class__.__name__ == 'Device')


def is_protect(device):
    """Target devices that are Nest Protect Smoke Alarms."""
    return bool(device.__class__.__name__ == 'ProtectDevice')


class NestSensor(Entity):
    """Representation of a Nest sensor."""

    def __init__(self, structure, device, variable):
        """Initialize the sensor."""
        self.structure = structure
        self.device = device
        self.variable = variable

    @property
    def name(self):
        """Return the name of the nest, if any."""
        location = self.device.where
        name = self.device.name
        if location is None:
            return "{} {}".format(name, self.variable)
        else:
            if name == '':
                return "{} {}".format(location.capitalize(), self.variable)
            else:
                return "{}({}){}".format(location.capitalize(),
                                         name,
                                         self.variable)


class NestBasicSensor(NestSensor):
    """Representation a basic Nest sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return getattr(self.device, self.variable)

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return SENSOR_UNITS.get(self.variable, None)


class NestTempSensor(NestSensor):
    """Representation of a Nest Temperature sensor."""

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return TEMP_CELSIUS

    @property
    def state(self):
        """Return the state of the sensor."""
        temp = getattr(self.device, self.variable)
        if temp is None:
            return None

        return round(temp, 1)


class NestWeatherSensor(NestSensor):
    """Representation a basic Nest Weather Conditions sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.variable == 'kph' or self.variable == 'direction':
            return getattr(self.structure.weather.current.wind, self.variable)
        else:
            return getattr(self.structure.weather.current, self.variable)

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return SENSOR_UNITS.get(self.variable, None)


class NestProtectSensor(NestSensor):
    """Return the state of nest protect."""

    @property
    def state(self):
        """Return the state of the sensor."""
        state = getattr(self.device, self.variable)
        if self.variable == 'battery_level':
            return getattr(self.device, self.variable)
        else:
            if state == 0:
                return 'Ok'
            if state == 1 or state == 2:
                return 'Warning'
            if state == 3:
                return 'Emergency'

        return 'Unknown'

    @property
    def name(self):
        """Return the name of the nest, if any."""
        return "{} {}".format(self.device.where.capitalize(), self.variable)
