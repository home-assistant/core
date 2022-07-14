"""Sensor from an SQL Query."""
from __future__ import annotations

from datetime import date
import decimal
import logging

import sqlalchemy
from sqlalchemy.engine import Result
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import scoped_session, sessionmaker

from homeassistant.components.recorder import CONF_DB_URL
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_UNIT_OF_MEASUREMENT, CONF_VALUE_TEMPLATE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.template import Template

from .const import CONF_COLUMN_NAME, CONF_QUERY, DB_URL_RE, DOMAIN

_LOGGER = logging.getLogger(__name__)


def redact_credentials(data: str) -> str:
    """Redact credentials from string data."""
    return DB_URL_RE.sub("//****:****@", data)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the SQL sensor entry."""

    db_url: str = entry.options[CONF_DB_URL]
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

    try:
        engine = sqlalchemy.create_engine(db_url, future=True)
        sessmaker = scoped_session(sessionmaker(bind=engine, future=True))
    except SQLAlchemyError as err:
        _LOGGER.error("Can not open database %s", {redact_credentials(str(err))})
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
                entry.entry_id,
            )
        ],
        True,
    )


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
        entry_id: str,
    ) -> None:
        """Initialize the SQL sensor."""
        self._query = query
        self._attr_native_unit_of_measurement = unit
        self._template = value_template
        self._column_name = column
        self.sessionmaker = sessmaker
        self._attr_extra_state_attributes = {}
        self._attr_unique_id = entry_id
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_id)},
            manufacturer="SQL",
            name=name,
        )

    def update(self) -> None:
        """Retrieve sensor data from the query."""

        data = None
        self._attr_extra_state_attributes = {}
        sess: scoped_session = self.sessionmaker()
        try:
            result: Result = sess.execute(sqlalchemy.text(self._query))
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
                if isinstance(value, date):
                    value = value.isoformat()
                self._attr_extra_state_attributes[key] = value

        if data is not None and self._template is not None:
            self._attr_native_value = (
                self._template.async_render_with_possible_json_value(data, None)
            )
        else:
            self._attr_native_value = data

        if data is None:
            _LOGGER.warning("%s returned no results", self._query)

        sess.close()
