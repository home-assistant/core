"""InfluxDB component which allows you to get data from an Influx database."""
from datetime import timedelta
import logging
from typing import Dict

from influxdb import InfluxDBClient, exceptions
from influxdb_client import InfluxDBClient as InfluxDBClientV2
from influxdb_client.rest import ApiException
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_API_VERSION,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_PORT,
    CONF_SSL,
    CONF_TOKEN,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_URL,
    CONF_USERNAME,
    CONF_VALUE_TEMPLATE,
    CONF_VERIFY_SSL,
    STATE_UNKNOWN,
)
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

from . import (
    API_VERSION_2,
    COMPONENT_CONFIG_SCHEMA_CONNECTION,
    CONF_BUCKET,
    CONF_DB_NAME,
    CONF_ORG,
    DEFAULT_API_VERSION,
    create_influx_url,
    validate_version_specific_config,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_GROUP_FUNCTION = "mean"
DEFAULT_FIELD = "value"

CONF_QUERIES = "queries"
CONF_QUERIES_FLUX = "queries_flux"
CONF_GROUP_FUNCTION = "group_function"
CONF_FIELD = "field"
CONF_MEASUREMENT_NAME = "measurement"
CONF_WHERE = "where"

CONF_RANGE_START = "range_start"
CONF_RANGE_STOP = "range_stop"
CONF_FUNCTION = "function"
CONF_QUERY = "query"
CONF_IMPORTS = "imports"

DEFAULT_RANGE_START = "-15m"
DEFAULT_RANGE_STOP = "now()"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

_QUERY_SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    }
)

_QUERY_SCHEMA = {
    "InfluxQL": _QUERY_SENSOR_SCHEMA.extend(
        {
            vol.Optional(CONF_DB_NAME): cv.string,
            vol.Required(CONF_MEASUREMENT_NAME): cv.string,
            vol.Optional(
                CONF_GROUP_FUNCTION, default=DEFAULT_GROUP_FUNCTION
            ): cv.string,
            vol.Optional(CONF_FIELD, default=DEFAULT_FIELD): cv.string,
            vol.Required(CONF_WHERE): cv.template,
        }
    ),
    "Flux": _QUERY_SENSOR_SCHEMA.extend(
        {
            vol.Optional(CONF_BUCKET): cv.string,
            vol.Optional(CONF_RANGE_START, default=DEFAULT_RANGE_START): cv.string,
            vol.Optional(CONF_RANGE_STOP, default=DEFAULT_RANGE_STOP): cv.string,
            vol.Required(CONF_QUERY): cv.template,
            vol.Optional(CONF_IMPORTS): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(CONF_GROUP_FUNCTION): cv.string,
        }
    ),
}


def validate_query_format_for_version(conf: Dict) -> Dict:
    """Ensure queries are provided in correct format based on API version."""
    if conf[CONF_API_VERSION] == API_VERSION_2:
        if CONF_QUERIES_FLUX not in conf:
            raise vol.Invalid(
                f"{CONF_QUERIES_FLUX} is required when {CONF_API_VERSION} is {API_VERSION_2}"
            )

    else:
        if CONF_QUERIES not in conf:
            raise vol.Invalid(
                f"{CONF_QUERIES} is required when {CONF_API_VERSION} is {DEFAULT_API_VERSION}"
            )

    return conf


PLATFORM_SCHEMA = vol.All(
    PLATFORM_SCHEMA.extend(COMPONENT_CONFIG_SCHEMA_CONNECTION).extend(
        {
            vol.Exclusive(CONF_QUERIES, "queries"): [_QUERY_SCHEMA["InfluxQL"]],
            vol.Exclusive(CONF_QUERIES_FLUX, "queries"): [_QUERY_SCHEMA["Flux"]],
        }
    ),
    validate_version_specific_config,
    validate_query_format_for_version,
    create_influx_url,
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the InfluxDB component."""
    use_v2_api = config[CONF_API_VERSION] == API_VERSION_2
    queries = None

    if use_v2_api:
        influx_conf = {
            "url": config[CONF_URL],
            "token": config[CONF_TOKEN],
            "org": config[CONF_ORG],
        }
        bucket = config[CONF_BUCKET]
        queries = config[CONF_QUERIES_FLUX]

        for v2_query in queries:
            if CONF_BUCKET not in v2_query:
                v2_query[CONF_BUCKET] = bucket

    else:
        influx_conf = {
            "database": config[CONF_DB_NAME],
            "verify_ssl": config[CONF_VERIFY_SSL],
        }

        if CONF_USERNAME in config:
            influx_conf["username"] = config[CONF_USERNAME]

        if CONF_PASSWORD in config:
            influx_conf["password"] = config[CONF_PASSWORD]

        if CONF_HOST in config:
            influx_conf["host"] = config[CONF_HOST]

        if CONF_PATH in config:
            influx_conf["path"] = config[CONF_PATH]

        if CONF_PORT in config:
            influx_conf["port"] = config[CONF_PORT]

        if CONF_SSL in config:
            influx_conf["ssl"] = config[CONF_SSL]

        queries = config[CONF_QUERIES]

    entities = []
    for query in queries:
        sensor = InfluxSensor(hass, influx_conf, query, use_v2_api)
        if sensor.connected:
            entities.append(sensor)

    add_entities(entities, True)


class InfluxSensor(Entity):
    """Implementation of a Influxdb sensor."""

    def __init__(self, hass, influx_conf, query, use_v2_api):
        """Initialize the sensor."""
        self._name = query.get(CONF_NAME)
        self._unit_of_measurement = query.get(CONF_UNIT_OF_MEASUREMENT)
        value_template = query.get(CONF_VALUE_TEMPLATE)
        if value_template is not None:
            self._value_template = value_template
            self._value_template.hass = hass
        else:
            self._value_template = None
        self._state = None
        self._hass = hass

        if use_v2_api:
            influx = InfluxDBClientV2(**influx_conf)
            query_api = influx.query_api()
            query_clause = query.get(CONF_QUERY)
            query_clause.hass = hass
            bucket = query[CONF_BUCKET]

        else:
            if CONF_DB_NAME in query:
                kwargs = influx_conf.copy()
                kwargs[CONF_DB_NAME] = query[CONF_DB_NAME]
            else:
                kwargs = influx_conf

            influx = InfluxDBClient(**kwargs)
            where_clause = query.get(CONF_WHERE)
            where_clause.hass = hass
            query_api = None

        try:
            if query_api is not None:
                query_api.query(
                    f'from(bucket: "{bucket}") |> range(start: -1ms) |> keep(columns: ["_time"]) |> limit(n: 1)'
                )
                self.connected = True
                self.data = InfluxSensorDataV2(
                    query_api,
                    bucket,
                    query.get(CONF_RANGE_START),
                    query.get(CONF_RANGE_STOP),
                    query_clause,
                    query.get(CONF_IMPORTS),
                    query.get(CONF_GROUP_FUNCTION),
                )

            else:
                influx.query("SHOW SERIES LIMIT 1;")
                self.connected = True
                self.data = InfluxSensorDataV1(
                    influx,
                    query.get(CONF_GROUP_FUNCTION),
                    query.get(CONF_FIELD),
                    query.get(CONF_MEASUREMENT_NAME),
                    where_clause,
                )
        except exceptions.InfluxDBClientError as exc:
            _LOGGER.error(
                "Database host is not accessible due to '%s', please"
                " check your entries in the configuration file and"
                " that the database exists and is READ/WRITE",
                exc,
            )
            self.connected = False
        except ApiException as exc:
            _LOGGER.error(
                "Bucket is not accessible due to '%s', please "
                "check your entries in the configuration file (url, org, "
                "bucket, etc.) and verify that the org and bucket exist and the "
                "provided token has READ access.",
                exc,
            )
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
                str(value), STATE_UNKNOWN
            )

        self._state = value


class InfluxSensorDataV2:
    """Class for handling the data retrieval with v2 API."""

    def __init__(
        self, query_api, bucket, range_start, range_stop, query, imports, group
    ):
        """Initialize the data object."""
        self.query_api = query_api
        self.bucket = bucket
        self.range_start = range_start
        self.range_stop = range_stop
        self.query = query
        self.imports = imports
        self.group = group
        self.value = None
        self.full_query = None

        self.query_prefix = f'from(bucket:"{bucket}") |> range(start: {range_start}, stop: {range_stop}) |>'
        if imports is not None:
            for i in imports:
                self.query_prefix = f'import "{i}" {self.query_prefix}'

        if group is None:
            self.query_postfix = "|> limit(n: 1)"
        else:
            self.query_postfix = f'|> {group}(column: "_value")'

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data by querying influx."""
        _LOGGER.debug("Rendering query: %s", self.query)
        try:
            rendered_query = self.query.render()
        except TemplateError as ex:
            _LOGGER.error("Could not render query template: %s", ex)
            return

        self.full_query = f"{self.query_prefix} {rendered_query} {self.query_postfix}"

        _LOGGER.info("Running query: %s", self.full_query)

        try:
            tables = self.query_api.query(self.full_query)
        except ApiException as exc:
            _LOGGER.error(
                "Could not execute query '%s' due to '%s', "
                "Check the syntax of your query",
                self.full_query,
                exc,
            )
            self.value = None
            return

        if not tables:
            _LOGGER.warning(
                "Query returned no results, sensor state set to UNKNOWN: %s",
                self.full_query,
            )
            self.value = None
        else:
            if len(tables) > 1:
                _LOGGER.warning(
                    "Query returned multiple tables, only value from first one is shown: %s",
                    self.full_query,
                )
            self.value = tables[0].records[0].values["_value"]


class InfluxSensorDataV1:
    """Class for handling the data retrieval with v1 API."""

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

        self.query = f"select {self.group}({self.field}) as value from {self.measurement} where {where_clause}"

        _LOGGER.info("Running query: %s", self.query)

        try:
            points = list(self.influx.query(self.query).get_points())
        except exceptions.InfluxDBClientError as exc:
            _LOGGER.error(
                "Could not execute query '%s' due to '%s', "
                "Check the syntax of your query",
                self.query,
                exc,
            )
            self.value = None
            return

        if not points:
            _LOGGER.warning(
                "Query returned no points, sensor state set to UNKNOWN: %s", self.query
            )
            self.value = None
        else:
            if len(points) > 1:
                _LOGGER.warning(
                    "Query returned multiple points, only first one shown: %s",
                    self.query,
                )
            self.value = points[0].get("value")
