"""Adds config flow for SQL integration."""

from __future__ import annotations

import logging
from typing import Any

import sqlalchemy
from sqlalchemy.engine import Result
from sqlalchemy.exc import MultipleResultsFound, NoSuchColumnError, SQLAlchemyError
from sqlalchemy.orm import Session, scoped_session, sessionmaker
import sqlparse
from sqlparse.exceptions import SQLParseError
import voluptuous as vol

from homeassistant.components.recorder import CONF_DB_URL, get_instance
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import CONF_COLUMN_NAME, CONF_QUERY, DOMAIN
from .util import resolve_db_url

_LOGGER = logging.getLogger(__name__)


OPTIONS_SCHEMA: vol.Schema = vol.Schema(
    {
        vol.Optional(
            CONF_DB_URL,
        ): selector.TextSelector(),
        vol.Required(
            CONF_COLUMN_NAME,
        ): selector.TextSelector(),
        vol.Required(
            CONF_QUERY,
        ): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
        vol.Optional(
            CONF_UNIT_OF_MEASUREMENT,
        ): selector.TextSelector(),
        vol.Optional(
            CONF_VALUE_TEMPLATE,
        ): selector.TemplateSelector(),
        vol.Optional(CONF_DEVICE_CLASS): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    cls.value
                    for cls in SensorDeviceClass
                    if cls != SensorDeviceClass.ENUM
                ],
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key="device_class",
                sort=True,
            )
        ),
        vol.Optional(CONF_STATE_CLASS): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[cls.value for cls in SensorStateClass],
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key="state_class",
                sort=True,
            )
        ),
    }
)

CONFIG_SCHEMA: vol.Schema = vol.Schema(
    {
        vol.Required(CONF_NAME, default="Select SQL Query"): selector.TextSelector(),
    }
).extend(OPTIONS_SCHEMA.schema)


def validate_sql_select(value: str) -> str:
    """Validate that value is a SQL SELECT query."""
    if len(query := sqlparse.parse(value.lstrip().lstrip(";"))) > 1:
        raise MultipleResultsFound
    if len(query) == 0 or (query_type := query[0].get_type()) == "UNKNOWN":
        raise ValueError
    if query_type != "SELECT":
        _LOGGER.debug("The SQL query %s is of type %s", query, query_type)
        raise SQLParseError
    return str(query[0])


def validate_query(db_url: str, query: str, column: str) -> bool:
    """Validate SQL query."""

    engine = sqlalchemy.create_engine(db_url, future=True)
    sessmaker = scoped_session(sessionmaker(bind=engine, future=True))
    sess: Session = sessmaker()

    try:
        result: Result = sess.execute(sqlalchemy.text(query))
    except SQLAlchemyError as error:
        _LOGGER.debug("Execution error %s", error)
        if sess:
            sess.close()
            engine.dispose()
        raise ValueError(error) from error

    for res in result.mappings():
        if column not in res:
            _LOGGER.debug("Column `%s` is not returned by the query", column)
            if sess:
                sess.close()
                engine.dispose()
            raise NoSuchColumnError(f"Column {column} is not returned by the query.")

        data = res[column]
        _LOGGER.debug("Return value from query: %s", data)

    if sess:
        sess.close()
        engine.dispose()

    return True


class SQLConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SQL integration."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SQLOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SQLOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        errors = {}
        description_placeholders = {}

        if user_input is not None:
            db_url = user_input.get(CONF_DB_URL)
            query = user_input[CONF_QUERY]
            column = user_input[CONF_COLUMN_NAME]
            db_url_for_validation = None

            try:
                query = validate_sql_select(query)
                db_url_for_validation = resolve_db_url(self.hass, db_url)
                await self.hass.async_add_executor_job(
                    validate_query, db_url_for_validation, query, column
                )
            except NoSuchColumnError:
                errors["column"] = "column_invalid"
                description_placeholders = {"column": column}
            except MultipleResultsFound:
                errors["query"] = "multiple_queries"
            except SQLAlchemyError:
                errors["db_url"] = "db_url_invalid"
            except SQLParseError:
                errors["query"] = "query_no_read_only"
            except ValueError as err:
                _LOGGER.debug("Invalid query: %s", err)
                errors["query"] = "query_invalid"

            options = {
                CONF_QUERY: query,
                CONF_COLUMN_NAME: column,
                CONF_NAME: user_input[CONF_NAME],
            }
            if uom := user_input.get(CONF_UNIT_OF_MEASUREMENT):
                options[CONF_UNIT_OF_MEASUREMENT] = uom
            if value_template := user_input.get(CONF_VALUE_TEMPLATE):
                options[CONF_VALUE_TEMPLATE] = value_template
            if device_class := user_input.get(CONF_DEVICE_CLASS):
                options[CONF_DEVICE_CLASS] = device_class
            if state_class := user_input.get(CONF_STATE_CLASS):
                options[CONF_STATE_CLASS] = state_class
            if db_url_for_validation != get_instance(self.hass).db_url:
                options[CONF_DB_URL] = db_url_for_validation

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={},
                    options=options,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(CONFIG_SCHEMA, user_input),
            errors=errors,
            description_placeholders=description_placeholders,
        )


class SQLOptionsFlowHandler(OptionsFlow):
    """Handle SQL options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage SQL options."""
        errors = {}
        description_placeholders = {}

        if user_input is not None:
            db_url = user_input.get(CONF_DB_URL)
            query = user_input[CONF_QUERY]
            column = user_input[CONF_COLUMN_NAME]
            name = self.config_entry.options.get(CONF_NAME, self.config_entry.title)

            try:
                query = validate_sql_select(query)
                db_url_for_validation = resolve_db_url(self.hass, db_url)
                await self.hass.async_add_executor_job(
                    validate_query, db_url_for_validation, query, column
                )
            except NoSuchColumnError:
                errors["column"] = "column_invalid"
                description_placeholders = {"column": column}
            except MultipleResultsFound:
                errors["query"] = "multiple_queries"
            except SQLAlchemyError:
                errors["db_url"] = "db_url_invalid"
            except SQLParseError:
                errors["query"] = "query_no_read_only"
            except ValueError as err:
                _LOGGER.debug("Invalid query: %s", err)
                errors["query"] = "query_invalid"
            else:
                recorder_db = get_instance(self.hass).db_url
                _LOGGER.debug(
                    "db_url: %s, resolved db_url: %s, recorder: %s",
                    db_url,
                    db_url_for_validation,
                    recorder_db,
                )

                options = {
                    CONF_QUERY: query,
                    CONF_COLUMN_NAME: column,
                    CONF_NAME: name,
                }
                if uom := user_input.get(CONF_UNIT_OF_MEASUREMENT):
                    options[CONF_UNIT_OF_MEASUREMENT] = uom
                if value_template := user_input.get(CONF_VALUE_TEMPLATE):
                    options[CONF_VALUE_TEMPLATE] = value_template
                if device_class := user_input.get(CONF_DEVICE_CLASS):
                    options[CONF_DEVICE_CLASS] = device_class
                if state_class := user_input.get(CONF_STATE_CLASS):
                    options[CONF_STATE_CLASS] = state_class
                if db_url_for_validation != get_instance(self.hass).db_url:
                    options[CONF_DB_URL] = db_url_for_validation

                return self.async_create_entry(
                    data=options,
                )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, user_input or self.config_entry.options
            ),
            errors=errors,
            description_placeholders=description_placeholders,
        )
