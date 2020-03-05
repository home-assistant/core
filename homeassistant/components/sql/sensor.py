"""Sensor from an SQL Query."""
import datetime
import decimal
import logging

import sqlalchemy
from sqlalchemy.orm import scoped_session, sessionmaker
import voluptuous as vol

from homeassistant.exceptions import TemplateError
from homeassistant.components.recorder import (
    CONF_DB_URL,
    DEFAULT_DB_FILE,
    DEFAULT_URL,
)

from homeassistant.components.sensor import PLATFORM_SCHEMA

from homeassistant.const import (
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
)

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

CONF_COLUMN_NAME = "column"
CONF_QUERIES = "queries"
CONF_QUERY = "query"
CONF_QUERY_TEMPLATE = "query_template"


def validate_sql(value):
    """Validate that value is a SQL SELECT query."""
    if not value.lstrip().lower().startswith(
        "select"
    ) and not value.lstrip().lower().startswith("exec"):
        raise Exception("Only SELECT or EXEC queries allowed")
    return value


_QUERY_SCHEME = vol.Schema(
    {
        vol.Required(CONF_COLUMN_NAME): cv.string,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_QUERY): cv.string,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_QUERY_TEMPLATE): cv.template,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_QUERIES): [_QUERY_SCHEME], vol.Optional(CONF_DB_URL): cv.string}
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the SQL sensor platform."""
    db_url = config.get(CONF_DB_URL, None)

    if not db_url:
        db_url = DEFAULT_URL.format(hass_config_path=hass.config.path(DEFAULT_DB_FILE))
    try:
        engine = sqlalchemy.create_engine(db_url)
        sessmaker = scoped_session(sessionmaker(bind=engine))

        # Run a dummy query just to test the db_url
        sess = sessmaker()
        sess.execute("SELECT 1;")
    except sqlalchemy.exc.SQLAlchemyError as err:
        _LOGGER.error("Couldn't connect using %s DB_URL: %s", db_url, err)
        return
    finally:
        sess.close()
    queries = []

    for query in config.get(CONF_QUERIES):
        name = query.get(CONF_NAME)
        query_str = query.get(CONF_QUERY)
        unit = query.get(CONF_UNIT_OF_MEASUREMENT)
        value_template = query.get(CONF_VALUE_TEMPLATE)
        column_name = query.get(CONF_COLUMN_NAME)
        query_template = query.get(CONF_QUERY_TEMPLATE)

        if query_str and query_template:
            raise Exception("Both query and query_template are defined. Choose one.")
        if value_template is not None:
            value_template.hass = hass
        if query_template is not None:
            query_template.hass = hass
        sensor = SQLSensor(
            hass,
            name,
            sessmaker,
            query_str,
            column_name,
            unit,
            value_template,
            query_template,
        )
        queries.append(sensor)
    async_add_entities(queries)

    return True


class SQLSensor(Entity):
    """Representation of an SQL sensor."""

    def __init__(
        self, hass, name, sessmaker, query, column, unit, value_template, query_template
    ):
        """Initialize the SQL sensor."""
        self.hass = hass
        self._name = name
        self._query_template = query_template

        if query is not None:
            if "LIMIT" in query:
                self._query = query
            else:
                self._query = query.replace(";", " LIMIT 1;")
        else:
            self._query = None
        self._unit_of_measurement = unit
        self._template = value_template
        self._column_name = column
        self.sessionmaker = sessmaker
        self._state = None
        self._attributes = {}

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

    async def async_update(self):
        """Retrieve sensor data from the query."""

        if self._query is not None:
            sql_command = self._query
        if self._query_template is not None:
            try:
                sql_command = self._query_template.async_render()
            except TemplateError as ex:
                if ex.args and ex.args[0].startswith(
                    "UndefinedError: 'None' has no attribute"
                ):
                    # Common during HA startup - so just a warning
                    _LOGGER.warning(
                        "Could not render template %s, the state is unknown.",
                        self._name,
                    )
                else:
                    self._state = None
                    _LOGGER.error("Could not render template %s: %s", self._name, ex)
        try:
            validated_sql_command = validate_sql(sql_command)
            sess = self.sessionmaker()
            result = sess.execute(validated_sql_command)
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
                data, None
            )
        else:
            self._state = data
