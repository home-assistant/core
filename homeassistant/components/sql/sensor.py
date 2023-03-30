"""Sensor from an SQL Query."""
from __future__ import annotations

from datetime import date
import decimal
import logging

import sqlalchemy
from sqlalchemy import lambda_stmt
from sqlalchemy.engine import Result
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, scoped_session, sessionmaker
from sqlalchemy.sql.lambdas import StatementLambdaElement
from sqlalchemy.util import LRUCache

from homeassistant.components.recorder import CONF_DB_URL, get_instance
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_COLUMN_NAME, CONF_QUERY, DB_URL_RE, DOMAIN
from .util import resolve_db_url

_LOGGER = logging.getLogger(__name__)

_SQL_LAMBDA_CACHE: LRUCache = LRUCache(1000)


def redact_credentials(data: str) -> str:
    """Redact credentials from string data."""
    return DB_URL_RE.sub("//****:****@", data)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the SQL sensor from yaml."""
    if (conf := discovery_info) is None:
        return

    name: str = conf[CONF_NAME]
    query_str: str = conf[CONF_QUERY]
    unit: str | None = conf.get(CONF_UNIT_OF_MEASUREMENT)
    value_template: Template | None = conf.get(CONF_VALUE_TEMPLATE)
    column_name: str = conf[CONF_COLUMN_NAME]
    unique_id: str | None = conf.get(CONF_UNIQUE_ID)
    db_url: str = resolve_db_url(hass, conf.get(CONF_DB_URL))
    device_class: SensorDeviceClass | None = conf.get(CONF_DEVICE_CLASS)
    state_class: SensorStateClass | None = conf.get(CONF_STATE_CLASS)

    if value_template is not None:
        value_template.hass = hass

    await async_setup_sensor(
        hass,
        name,
        query_str,
        column_name,
        unit,
        value_template,
        unique_id,
        db_url,
        True,
        device_class,
        state_class,
        async_add_entities,
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the SQL sensor from config entry."""

    db_url: str = resolve_db_url(hass, entry.options.get(CONF_DB_URL))
    name: str = entry.options[CONF_NAME]
    query_str: str = entry.options[CONF_QUERY]
    unit: str | None = entry.options.get(CONF_UNIT_OF_MEASUREMENT)
    template: str | None = entry.options.get(CONF_VALUE_TEMPLATE)
    column_name: str = entry.options[CONF_COLUMN_NAME]

    value_template: Template | None = None
    if template is not None:
        try:
            value_template = Template(template)
            value_template.ensure_valid()
        except TemplateError:
            value_template = None
        if value_template is not None:
            value_template.hass = hass

    await async_setup_sensor(
        hass,
        name,
        query_str,
        column_name,
        unit,
        value_template,
        entry.entry_id,
        db_url,
        False,
        None,
        None,
        async_add_entities,
    )


async def async_setup_sensor(
    hass: HomeAssistant,
    name: str,
    query_str: str,
    column_name: str,
    unit: str | None,
    value_template: Template | None,
    unique_id: str | None,
    db_url: str,
    yaml: bool,
    device_class: SensorDeviceClass | None,
    state_class: SensorStateClass | None,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SQL sensor."""
    instance = get_instance(hass)
    sessmaker: scoped_session | None
    if use_database_executor := (db_url == instance.db_url):
        assert instance.engine is not None
        sessmaker = scoped_session(sessionmaker(bind=instance.engine, future=True))
    elif not (
        sessmaker := await hass.async_add_executor_job(
            _validate_and_get_session_maker_for_db_url, db_url
        )
    ):
        return

    # MSSQL uses TOP and not LIMIT
    if not ("LIMIT" in query_str.upper() or "SELECT TOP" in query_str.upper()):
        if "mssql" in db_url:
            query_str = query_str.upper().replace("SELECT", "SELECT TOP 1")
        else:
            query_str = query_str.replace(";", "") + " LIMIT 1;"

    async_add_entities(
        [
            SQLSensor(
                name,
                sessmaker,
                query_str,
                column_name,
                unit,
                value_template,
                unique_id,
                yaml,
                device_class,
                state_class,
                use_database_executor,
            )
        ],
        True,
    )


def _validate_and_get_session_maker_for_db_url(db_url: str) -> scoped_session | None:
    """Validate the db_url and return a session maker.

    This does I/O and should be run in the executor.
    """
    sess: Session | None = None
    try:
        engine = sqlalchemy.create_engine(db_url, future=True)
        sessmaker = scoped_session(sessionmaker(bind=engine, future=True))
        # Run a dummy query just to test the db_url
        sess = sessmaker()
        sess.execute(sqlalchemy.text("SELECT 1;"))

    except SQLAlchemyError as err:
        _LOGGER.error(
            "Couldn't connect using %s DB_URL: %s",
            redact_credentials(db_url),
            redact_credentials(str(err)),
        )
        return None
    else:
        return sessmaker
    finally:
        if sess:
            sess.close()


def _generate_lambda_stmt(query: str) -> StatementLambdaElement:
    """Generate the lambda statement."""
    text = sqlalchemy.text(query)
    return lambda_stmt(lambda: text, lambda_cache=_SQL_LAMBDA_CACHE)


class SQLSensor(SensorEntity):
    """Representation of an SQL sensor."""

    _attr_icon = "mdi:database-search"
    _attr_has_entity_name = True

    def __init__(
        self,
        name: str,
        sessmaker: scoped_session,
        query: str,
        column: str,
        unit: str | None,
        value_template: Template | None,
        unique_id: str | None,
        yaml: bool,
        device_class: SensorDeviceClass | None,
        state_class: SensorStateClass | None,
        use_database_executor: bool,
    ) -> None:
        """Initialize the SQL sensor."""
        self._query = query
        self._attr_name = name if yaml else None
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._template = value_template
        self._column_name = column
        self.sessionmaker = sessmaker
        self._attr_extra_state_attributes = {}
        self._attr_unique_id = unique_id
        self._use_database_executor = use_database_executor
        self._lambda_stmt = _generate_lambda_stmt(query)
        if not yaml and unique_id:
            self._attr_device_info = DeviceInfo(
                entry_type=DeviceEntryType.SERVICE,
                identifiers={(DOMAIN, unique_id)},
                manufacturer="SQL",
                name=name,
            )

    async def async_update(self) -> None:
        """Retrieve sensor data from the query using the right executor."""
        if self._use_database_executor:
            await get_instance(self.hass).async_add_executor_job(self._update)
        else:
            await self.hass.async_add_executor_job(self._update)

    def _update(self) -> None:
        """Retrieve sensor data from the query."""
        data = None
        self._attr_extra_state_attributes = {}
        sess: scoped_session = self.sessionmaker()
        try:
            result: Result = sess.execute(self._lambda_stmt)
        except SQLAlchemyError as err:
            _LOGGER.error(
                "Error executing query %s: %s",
                self._query,
                redact_credentials(str(err)),
            )
            return

        for res in result.mappings():
            _LOGGER.debug("Query %s result in %s", self._query, res.items())
            data = res[self._column_name]
            for key, value in res.items():
                if isinstance(value, decimal.Decimal):
                    value = float(value)
                elif isinstance(value, date):
                    value = value.isoformat()
                elif isinstance(value, (bytes, bytearray)):
                    value = f"0x{value.hex()}"
                self._attr_extra_state_attributes[key] = value

        if data is not None and isinstance(data, (bytes, bytearray)):
            data = f"0x{data.hex()}"

        if data is not None and self._template is not None:
            self._attr_native_value = (
                self._template.async_render_with_possible_json_value(data, None)
            )
        else:
            self._attr_native_value = data

        if data is None:
            _LOGGER.warning("%s returned no results", self._query)

        sess.close()
