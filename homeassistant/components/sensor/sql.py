"""
Sensor from an SQL Query.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.sql/
"""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_UNIT_OF_MEASUREMENT, CONF_VALUE_TEMPLATE,
    STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['sqlalchemy==1.2.2']

DEFAULT_URL = 'sqlite:///{hass_config_path}/home-assistant_v2.db'
DEFAULT_NAME = 'Sql_sensor'

CONF_QUERIES = 'queries'
CONF_QUERY = 'query'
CONF_COLUMN_NAME = 'column'
CONF_DB_URL = 'db_url'

_QUERY_SCHEME = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_QUERY): cv.string,
    vol.Required(CONF_COLUMN_NAME): cv.string,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_QUERIES): [_QUERY_SCHEME],
    vol.Optional(CONF_DB_URL, default=DEFAULT_URL): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""
    db_url = config.get(CONF_DB_URL)
    queries = []

    for query in config.get(CONF_QUERIES):
        name = query.get(CONF_NAME)
        query_str = query.get(CONF_QUERY)
        unit = query.get(CONF_UNIT_OF_MEASUREMENT)
        value_template = query.get(CONF_VALUE_TEMPLATE)
        column_name = query.get(CONF_COLUMN_NAME)

        if value_template is not None:
            value_template.hass = hass

        sensor = SQLSensor(
            name, db_url, query_str, column_name, unit, value_template
            )
        queries.append(sensor)

    add_devices(queries, True)


class SQLSensor(Entity):
    """An SQL sensor."""

    def __init__(self, name, db_url, query, column, unit, value_template):
        """Initialize SQL sensor."""
        self._name = name
        if "LIMIT" in query:
            self._query = query
        else:
            self._query = query.replace(";", " LIMIT 1;")
        self._unit_of_measurement = unit
        self._template = value_template
        self._column_name = column

        import sqlalchemy
        from sqlalchemy.orm import sessionmaker, scoped_session

        engine = sqlalchemy.create_engine(db_url)
        self.session = scoped_session(sessionmaker(bind=engine))

        self._state = STATE_UNKNOWN
        self._attributes = None

    @property
    def name(self):
        """Return the name of the query."""
        return self._name

    @property
    def state(self):
        """Return the query's current state."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    def update(self):
        """Retrieve sensor data from the query."""
        sess = self.session()
        result = sess.execute(self._query)

        for res in result:
            _LOGGER.debug(res.items())
            data = res[self._column_name]
            self._attributes = {k: str(v) for k, v in res.items()}

        if data is None:
            _LOGGER.error("%s returned no results", self._query)
            return False

        if self._template is not None:
            self._state = self._template.async_render_with_possible_json_value(
                data, None)
        else:
            self._state = data

        sess.close()
