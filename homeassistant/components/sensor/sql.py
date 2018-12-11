"""
Sensor from an SQL Query.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.sql/
"""
import decimal
import datetime
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_UNIT_OF_MEASUREMENT, CONF_VALUE_TEMPLATE)
from homeassistant.components.recorder import (
    CONF_DB_URL, DEFAULT_URL, DEFAULT_DB_FILE)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['sqlalchemy==1.2.14']

CONF_COLUMN_NAME = 'column'
CONF_QUERIES = 'queries'
CONF_QUERY = 'query'


def validate_sql_select(value):
    """Validate that value is a SQL SELECT query."""
    if not value.lstrip().lower().startswith('select'):
        raise vol.Invalid('Only SELECT queries allowed')
    return value


_QUERY_SCHEME = vol.Schema({
    vol.Required(CONF_COLUMN_NAME): cv.string,
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_QUERY): vol.All(cv.string, validate_sql_select),
    vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_QUERIES): [_QUERY_SCHEME],
    vol.Optional(CONF_DB_URL): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the SQL sensor platform."""
    db_url = config.get(CONF_DB_URL, None)
    if not db_url:
        db_url = DEFAULT_URL.format(
            hass_config_path=hass.config.path(DEFAULT_DB_FILE))

    import sqlalchemy
    from sqlalchemy.orm import sessionmaker, scoped_session

    try:
        engine = sqlalchemy.create_engine(db_url)
        sessionmaker = scoped_session(sessionmaker(bind=engine))

        # Run a dummy query just to test the db_url
        sess = sessionmaker()
        sess.execute("SELECT 1;")

    except sqlalchemy.exc.SQLAlchemyError as err:
        _LOGGER.error("Couldn't connect using %s DB_URL: %s", db_url, err)
        return

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
            name, sessionmaker, query_str, column_name, unit, value_template
            )
        queries.append(sensor)

    add_entities(queries, True)


class SQLSensor(Entity):
    """Representation of an SQL sensor."""

    def __init__(self, name, sessmaker, query, column, unit, value_template):
        """Initialize the SQL sensor."""
        self._name = name
        if "LIMIT" in query:
            self._query = query
        else:
            self._query = query.replace(";", " LIMIT 1;")
        self._unit_of_measurement = unit
        self._template = value_template
        self._column_name = column
        self.sessionmaker = sessmaker
        self._state = None
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
        import sqlalchemy
        try:
            sess = self.sessionmaker()
            result = sess.execute(self._query)
            self._attributes = {}

            if not result.returns_rows or result.rowcount == 0:
                _LOGGER.warning("%s returned no results", self._query)
                self._state = None
                return

            for res in result:
                _LOGGER.debug("result = %s", res.items())
                data = res[self._column_name]
                for key, value in res.items():
                    if isinstance(value, decimal.Decimal):
                        value = float(value)
                    if isinstance(value, datetime.date):
                        value = str(value)
                    self._attributes[key] = value
        except sqlalchemy.exc.SQLAlchemyError as err:
            _LOGGER.error("Error executing query %s: %s", self._query, err)
            return
        finally:
            sess.close()

        if self._template is not None:
            self._state = self._template.async_render_with_possible_json_value(
                data, None)
        else:
            self._state = data
