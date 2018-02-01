"""
InfluxDB component which allows you to get data from an Influx database.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor.influxdb/
"""
import logging
from datetime import timedelta

import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_HOST, CONF_PORT, CONF_USERNAME,
                                 CONF_PASSWORD, CONF_SSL, CONF_VERIFY_SSL,
                                 CONF_NAME, CONF_UNIT_OF_MEASUREMENT,
                                 CONF_VALUE_TEMPLATE)
from homeassistant.const import STATE_UNKNOWN
from homeassistant.util import Throttle

from homeassistant.exceptions import TemplateError
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['influxdb==4.1.1']

DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 8086
DEFAULT_DATABASE = 'home_assistant'
DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = False
DEFAULT_GROUP_FUNCTION = 'mean'
DEFAULT_FIELD = 'value'

CONF_DB_NAME = 'database'
CONF_QUERIES = 'queries'
CONF_GROUP_FUNCTION = 'group_function'
CONF_FIELD = 'field'
CONF_MEASUREMENT_NAME = 'measurement'
CONF_WHERE = 'where'


_QUERY_SCHEME = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_MEASUREMENT_NAME): cv.string,
    vol.Required(CONF_WHERE): cv.template,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_DB_NAME, default=DEFAULT_DATABASE): cv.string,
    vol.Optional(CONF_GROUP_FUNCTION, default=DEFAULT_GROUP_FUNCTION):
        cv.string,
    vol.Optional(CONF_FIELD, default=DEFAULT_FIELD): cv.string
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_QUERIES): [_QUERY_SCHEME],
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Inclusive(CONF_USERNAME, 'authentication'): cv.string,
    vol.Inclusive(CONF_PASSWORD, 'authentication'): cv.string,
    vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean
})

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the InfluxDB component."""
    influx_conf = {
        'host': config[CONF_HOST],
        'password': config.get(CONF_PASSWORD),
        'port': config.get(CONF_PORT),
        'ssl': config.get(CONF_SSL),
        'username': config.get(CONF_USERNAME),
        'verify_ssl': config.get(CONF_VERIFY_SSL),
    }

    dev = []

    for query in config.get(CONF_QUERIES):
        sensor = InfluxSensor(hass, influx_conf, query)
        if sensor.connected:
            dev.append(sensor)

    add_devices(dev, True)


class InfluxSensor(Entity):
    """Implementation of a Influxdb sensor."""

    def __init__(self, hass, influx_conf, query):
        """Initialize the sensor."""
        from influxdb import InfluxDBClient, exceptions
        self._name = query.get(CONF_NAME)
        self._unit_of_measurement = query.get(CONF_UNIT_OF_MEASUREMENT)
        value_template = query.get(CONF_VALUE_TEMPLATE)
        if value_template is not None:
            self._value_template = value_template
            self._value_template.hass = hass
        else:
            self._value_template = None
        database = query.get(CONF_DB_NAME)
        self._state = None
        self._hass = hass

        where_clause = query.get(CONF_WHERE)
        where_clause.hass = hass

        influx = InfluxDBClient(
            host=influx_conf['host'], port=influx_conf['port'],
            username=influx_conf['username'], password=influx_conf['password'],
            database=database, ssl=influx_conf['ssl'],
            verify_ssl=influx_conf['verify_ssl'])
        try:
            influx.query("select * from /.*/ LIMIT 1;")
            self.connected = True
            self.data = InfluxSensorData(
                influx, query.get(CONF_GROUP_FUNCTION), query.get(CONF_FIELD),
                query.get(CONF_MEASUREMENT_NAME), where_clause)
        except exceptions.InfluxDBClientError as exc:
            _LOGGER.error("Database host is not accessible due to '%s', please"
                          " check your entries in the configuration file and"
                          " that the database exists and is READ/WRITE.", exc)
            self.connected = False

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
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    def update(self):
        """Get the latest data from Influxdb and updates the states."""
        self.data.update()
        value = self.data.value
        if value is None:
            value = STATE_UNKNOWN
        if self._value_template is not None:
            value = self._value_template.render_with_possible_json_value(
                str(value), STATE_UNKNOWN)

        self._state = value


class InfluxSensorData(object):
    """Class for handling the data retrieval."""

    def __init__(self, influx, group, field, measurement, where):
        """Initialize the data object."""
        self.influx = influx
        self.group = group
        self.field = field
        self.measurement = measurement
        self.where = where
        self.value = None
        self.query = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data with a shell command."""
        _LOGGER.info("Rendering where: %s", self.where)
        try:
            where_clause = self.where.render()
        except TemplateError as ex:
            _LOGGER.error("Could not render where clause template: %s", ex)
            return

        self.query = "select {}({}) as value from {} where {}".format(
            self.group, self.field, self.measurement, where_clause)

        _LOGGER.info("Running query: %s", self.query)

        points = list(self.influx.query(self.query).get_points())
        if not points:
            _LOGGER.warning("Query returned no points, sensor state set "
                            "to UNKNOWN: %s", self.query)
            self.value = None
        else:
            if len(points) > 1:
                _LOGGER.warning("Query returned multiple points, only first "
                                "one shown: %s", self.query)
            self.value = points[0].get('value')
