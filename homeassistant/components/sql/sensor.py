"""Sensor from an SQL Query."""

from __future__ import annotations

from datetime import date
import decimal
import logging
from typing import Any

from sqlalchemy.engine import Result
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import scoped_session

from homeassistant.components.recorder import CONF_DB_URL, get_instance
from homeassistant.components.sensor import CONF_STATE_CLASS
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_NAME,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
    MATCH_ALL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.template import Template
from homeassistant.helpers.trigger_template_entity import (
    CONF_AVAILABILITY,
    CONF_PICTURE,
    ManualTriggerSensorEntity,
    ValueTemplate,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_ADVANCED_OPTIONS, CONF_COLUMN_NAME, CONF_QUERY, DOMAIN
from .util import (
    async_create_sessionmaker,
    generate_lambda_stmt,
    redact_credentials,
    resolve_db_url,
    validate_query,
)

_LOGGER = logging.getLogger(__name__)

TRIGGER_ENTITY_OPTIONS = (
    CONF_AVAILABILITY,
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_PICTURE,
    CONF_UNIQUE_ID,
    CONF_STATE_CLASS,
    CONF_UNIT_OF_MEASUREMENT,
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the SQL sensor from yaml."""
    if (conf := discovery_info) is None:
        return

    name: Template = conf[CONF_NAME]
    query_str: str = conf[CONF_QUERY]
    value_template: ValueTemplate | None = conf.get(CONF_VALUE_TEMPLATE)
    column_name: str = conf[CONF_COLUMN_NAME]
    unique_id: str | None = conf.get(CONF_UNIQUE_ID)
    db_url: str = resolve_db_url(hass, conf.get(CONF_DB_URL))

    trigger_entity_config = {CONF_NAME: name}
    for key in TRIGGER_ENTITY_OPTIONS:
        if key not in conf:
            continue
        trigger_entity_config[key] = conf[key]

    await async_setup_sensor(
        hass,
        trigger_entity_config,
        query_str,
        column_name,
        value_template,
        unique_id,
        db_url,
        True,
        async_add_entities,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SQL sensor from config entry."""

    db_url: str = resolve_db_url(hass, entry.data.get(CONF_DB_URL))
    name: str = entry.title
    query_str: str = entry.options[CONF_QUERY]
    template: str | None = entry.options[CONF_ADVANCED_OPTIONS].get(CONF_VALUE_TEMPLATE)
    column_name: str = entry.options[CONF_COLUMN_NAME]

    value_template: ValueTemplate | None = None
    if template is not None:
        try:
            value_template = ValueTemplate(template, hass)
            value_template.ensure_valid()
        except TemplateError:
            value_template = None

    name_template = Template(name, hass)
    trigger_entity_config = {CONF_NAME: name_template, CONF_UNIQUE_ID: entry.entry_id}
    for key in TRIGGER_ENTITY_OPTIONS:
        if key not in entry.options[CONF_ADVANCED_OPTIONS]:
            continue
        trigger_entity_config[key] = entry.options[CONF_ADVANCED_OPTIONS][key]

    await async_setup_sensor(
        hass,
        trigger_entity_config,
        query_str,
        column_name,
        value_template,
        entry.entry_id,
        db_url,
        False,
        async_add_entities,
    )


async def async_setup_sensor(
    hass: HomeAssistant,
    trigger_entity_config: ConfigType,
    query_str: str,
    column_name: str,
    value_template: ValueTemplate | None,
    unique_id: str | None,
    db_url: str,
    yaml: bool,
    async_add_entities: AddEntitiesCallback | AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SQL sensor."""
    (
        sessmaker,
        uses_recorder_db,
        use_database_executor,
    ) = await async_create_sessionmaker(hass, db_url)
    if sessmaker is None:
        return
    validate_query(hass, query_str, uses_recorder_db, unique_id)

    upper_query = query_str.upper()
    # MSSQL uses TOP and not LIMIT
    if not ("LIMIT" in upper_query or "SELECT TOP" in upper_query):
        if "mssql" in db_url:
            query_str = upper_query.replace("SELECT", "SELECT TOP 1")
        else:
            query_str = query_str.replace(";", "") + " LIMIT 1;"

    async_add_entities(
        [
            SQLSensor(
                trigger_entity_config,
                sessmaker,
                query_str,
                column_name,
                value_template,
                yaml,
                use_database_executor,
            )
        ],
    )


class SQLSensor(ManualTriggerSensorEntity):
    """Representation of an SQL sensor."""

    _unrecorded_attributes = frozenset({MATCH_ALL})

    def __init__(
        self,
        trigger_entity_config: ConfigType,
        sessmaker: scoped_session,
        query: str,
        column: str,
        value_template: ValueTemplate | None,
        yaml: bool,
        use_database_executor: bool,
    ) -> None:
        """Initialize the SQL sensor."""
        super().__init__(self.hass, trigger_entity_config)
        self._query = query
        self._template = value_template
        self._column_name = column
        self.sessionmaker = sessmaker
        self._attr_extra_state_attributes = {}
        self._use_database_executor = use_database_executor
        self._lambda_stmt = generate_lambda_stmt(query)
        if not yaml and (unique_id := trigger_entity_config.get(CONF_UNIQUE_ID)):
            self._attr_name = None
            self._attr_has_entity_name = True
            self._attr_device_info = DeviceInfo(
                entry_type=DeviceEntryType.SERVICE,
                identifiers={(DOMAIN, unique_id)},
                manufacturer="SQL",
                name=self._rendered.get(CONF_NAME),
            )

    @property
    def name(self) -> str | None:
        """Name of the entity."""
        if self.has_entity_name:
            return self._attr_name
        return self._rendered.get(CONF_NAME)

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()
        await self.async_update()

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        return dict(self._attr_extra_state_attributes)

    async def async_update(self) -> None:
        """Retrieve sensor data from the query using the right executor."""
        if self._use_database_executor:
            await get_instance(self.hass).async_add_executor_job(self._update)
        else:
            await self.hass.async_add_executor_job(self._update)

    def _update(self) -> None:
        """Retrieve sensor data from the query."""
        data = None
        extra_state_attributes = {}
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
            sess.rollback()
            sess.close()
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
                extra_state_attributes[key] = value
                self._attr_extra_state_attributes[key] = value

        if data is not None and isinstance(data, (bytes, bytearray)):
            data = f"0x{data.hex()}"

        if data is not None and self._template is not None:
            variables = self._template_variables_with_value(data)
            if self._render_availability_template(variables):
                _value = self._template.async_render_as_value_template(
                    self.entity_id, variables, None
                )
                self._set_native_value_with_possible_timestamp(_value)
                self._process_manual_data(variables)
        else:
            self._attr_native_value = data

        if data is None:
            _LOGGER.warning("%s returned no results", self._query)

        sess.close()
