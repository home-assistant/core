"""InfluxDB component which allows you to get data from an Influx database."""

from __future__ import annotations

import datetime
import logging
from typing import Final

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import (
    CONF_API_VERSION,
    CONF_LANGUAGE,
    CONF_NAME,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady, TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle

from . import create_influx_url, get_influx_connection, validate_version_specific_config
from .const import (
    API_VERSION_2,
    COMPONENT_CONFIG_SCHEMA_CONNECTION,
    CONF_BUCKET,
    CONF_DB_NAME,
    CONF_FIELD,
    CONF_GROUP_FUNCTION,
    CONF_IMPORTS,
    CONF_MEASUREMENT_NAME,
    CONF_QUERIES,
    CONF_QUERIES_FLUX,
    CONF_QUERY,
    CONF_RANGE_START,
    CONF_RANGE_STOP,
    CONF_WHERE,
    DEFAULT_API_VERSION,
    DEFAULT_FIELD,
    DEFAULT_FUNCTION_FLUX,
    DEFAULT_GROUP_FUNCTION,
    DEFAULT_RANGE_START,
    DEFAULT_RANGE_STOP,
    INFLUX_CONF_VALUE,
    INFLUX_CONF_VALUE_V2,
    LANGUAGE_FLUX,
    LANGUAGE_INFLUXQL,
    MIN_TIME_BETWEEN_UPDATES,
    NO_BUCKET_ERROR,
    NO_DATABASE_ERROR,
    QUERY_MULTIPLE_RESULTS_MESSAGE,
    QUERY_NO_RESULTS_MESSAGE,
    RENDERING_QUERY_ERROR_MESSAGE,
    RENDERING_QUERY_MESSAGE,
    RENDERING_WHERE_ERROR_MESSAGE,
    RENDERING_WHERE_MESSAGE,
    RUNNING_QUERY_MESSAGE,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL: Final = datetime.timedelta(seconds=60)


def _merge_connection_config_into_query(conf, query):
    """Merge connection details into each configured query."""
    for key in conf:
        if key not in query and key not in [CONF_QUERIES, CONF_QUERIES_FLUX]:
            query[key] = conf[key]


def validate_query_format_for_version(conf: dict) -> dict:
    """Ensure queries are provided in correct format based on API version."""
    if conf[CONF_API_VERSION] == API_VERSION_2:
        if CONF_QUERIES_FLUX not in conf:
            raise vol.Invalid(
                f"{CONF_QUERIES_FLUX} is required when {CONF_API_VERSION} is"
                f" {API_VERSION_2}"
            )

        for query in conf[CONF_QUERIES_FLUX]:
            _merge_connection_config_into_query(conf, query)
            query[CONF_LANGUAGE] = LANGUAGE_FLUX

        del conf[CONF_BUCKET]

    else:
        if CONF_QUERIES not in conf:
            raise vol.Invalid(
                f"{CONF_QUERIES} is required when {CONF_API_VERSION} is"
                f" {DEFAULT_API_VERSION}"
            )

        for query in conf[CONF_QUERIES]:
            _merge_connection_config_into_query(conf, query)
            query[CONF_LANGUAGE] = LANGUAGE_INFLUXQL

        del conf[CONF_DB_NAME]

    return conf


_QUERY_SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    }
)

_QUERY_SCHEMA = {
    LANGUAGE_INFLUXQL: _QUERY_SENSOR_SCHEMA.extend(
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
    LANGUAGE_FLUX: _QUERY_SENSOR_SCHEMA.extend(
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

PLATFORM_SCHEMA = vol.All(
    SENSOR_PLATFORM_SCHEMA.extend(COMPONENT_CONFIG_SCHEMA_CONNECTION).extend(
        {
            vol.Exclusive(CONF_QUERIES, "queries"): [_QUERY_SCHEMA[LANGUAGE_INFLUXQL]],
            vol.Exclusive(CONF_QUERIES_FLUX, "queries"): [_QUERY_SCHEMA[LANGUAGE_FLUX]],
        }
    ),
    validate_version_specific_config,
    validate_query_format_for_version,
    create_influx_url,
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the InfluxDB component."""
    try:
        influx = get_influx_connection(config, test_read=True)
    except ConnectionError as exc:
        _LOGGER.error(exc)
        raise PlatformNotReady from exc

    entities = []
    if CONF_QUERIES_FLUX in config:
        for query in config[CONF_QUERIES_FLUX]:
            if query[CONF_BUCKET] in influx.data_repositories:
                entities.append(InfluxSensor(hass, influx, query))
            else:
                _LOGGER.error(NO_BUCKET_ERROR, query[CONF_BUCKET])
    else:
        for query in config[CONF_QUERIES]:
            if query[CONF_DB_NAME] in influx.data_repositories:
                entities.append(InfluxSensor(hass, influx, query))
            else:
                _LOGGER.error(NO_DATABASE_ERROR, query[CONF_DB_NAME])

    add_entities(entities, update_before_add=True)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, lambda _: influx.close())


class InfluxSensor(SensorEntity):
    """Implementation of a Influxdb sensor."""

    def __init__(self, hass, influx, query):
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
        self._attr_unique_id = query.get(CONF_UNIQUE_ID)

        if query[CONF_LANGUAGE] == LANGUAGE_FLUX:
            query_clause = query.get(CONF_QUERY)
            query_clause.hass = hass
            self.data = InfluxFluxSensorData(
                influx,
                query.get(CONF_BUCKET),
                query.get(CONF_RANGE_START),
                query.get(CONF_RANGE_STOP),
                query_clause,
                query.get(CONF_IMPORTS),
                query.get(CONF_GROUP_FUNCTION),
            )

        else:
            where_clause = query.get(CONF_WHERE)
            where_clause.hass = hass
            self.data = InfluxQLSensorData(
                influx,
                query.get(CONF_DB_NAME),
                query.get(CONF_GROUP_FUNCTION),
                query.get(CONF_FIELD),
                query.get(CONF_MEASUREMENT_NAME),
                where_clause,
            )

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def update(self) -> None:
        """Get the latest data from Influxdb and updates the states."""
        self.data.update()
        if (value := self.data.value) is None:
            value = None
        if self._value_template is not None:
            value = self._value_template.render_with_possible_json_value(
                str(value), None
            )

        self._state = value


class InfluxFluxSensorData:
    """Class for handling the data retrieval from Influx with Flux query."""

    def __init__(self, influx, bucket, range_start, range_stop, query, imports, group):
        """Initialize the data object."""
        self.influx = influx
        self.bucket = bucket
        self.range_start = range_start
        self.range_stop = range_stop
        self.query = query
        self.imports = imports
        self.group = group
        self.value = None
        self.full_query = None

        self.query_prefix = (
            f'from(bucket:"{bucket}") |> range(start: {range_start}, stop:'
            f" {range_stop}) |>"
        )
        if imports is not None:
            for i in imports:
                self.query_prefix = f'import "{i}" {self.query_prefix}'

        if group is None:
            self.query_postfix = DEFAULT_FUNCTION_FLUX
        else:
            self.query_postfix = f'|> {group}(column: "{INFLUX_CONF_VALUE_V2}")'

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data by querying influx."""
        _LOGGER.debug(RENDERING_QUERY_MESSAGE, self.query)
        try:
            rendered_query = self.query.render(parse_result=False)
        except TemplateError as ex:
            _LOGGER.error(RENDERING_QUERY_ERROR_MESSAGE, ex)
            return

        self.full_query = f"{self.query_prefix} {rendered_query} {self.query_postfix}"

        _LOGGER.debug(RUNNING_QUERY_MESSAGE, self.full_query)

        try:
            tables = self.influx.query(self.full_query)
        except (ConnectionError, ValueError) as exc:
            _LOGGER.error(exc)
            self.value = None
            return

        if not tables:
            _LOGGER.warning(QUERY_NO_RESULTS_MESSAGE, self.full_query)
            self.value = None
        else:
            if len(tables) > 1 or len(tables[0].records) > 1:
                _LOGGER.warning(QUERY_MULTIPLE_RESULTS_MESSAGE, self.full_query)
            self.value = tables[0].records[0].values[INFLUX_CONF_VALUE_V2]


class InfluxQLSensorData:
    """Class for handling the data retrieval with v1 API."""

    def __init__(self, influx, db_name, group, field, measurement, where):
        """Initialize the data object."""
        self.influx = influx
        self.db_name = db_name
        self.group = group
        self.field = field
        self.measurement = measurement
        self.where = where
        self.value = None
        self.query = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data with a shell command."""
        _LOGGER.debug(RENDERING_WHERE_MESSAGE, self.where)
        try:
            where_clause = self.where.render(parse_result=False)
        except TemplateError as ex:
            _LOGGER.error(RENDERING_WHERE_ERROR_MESSAGE, ex)
            return

        self.query = (
            f"select {self.group}({self.field}) as {INFLUX_CONF_VALUE} from"  # noqa: S608
            f" {self.measurement} where {where_clause}"
        )

        _LOGGER.debug(RUNNING_QUERY_MESSAGE, self.query)

        try:
            points = self.influx.query(self.query, self.db_name)
        except (ConnectionError, ValueError) as exc:
            _LOGGER.error(exc)
            self.value = None
            return

        if not points:
            _LOGGER.warning(QUERY_NO_RESULTS_MESSAGE, self.query)
            self.value = None
        else:
            if len(points) > 1:
                _LOGGER.warning(QUERY_MULTIPLE_RESULTS_MESSAGE, self.query)
            self.value = points[0].get(INFLUX_CONF_VALUE)
