"""Adds config flow for SQL integration."""

from __future__ import annotations

import logging
from typing import Any

import sqlalchemy
from sqlalchemy.engine import Engine, Result
from sqlalchemy.exc import MultipleResultsFound, NoSuchColumnError, SQLAlchemyError
from sqlalchemy.orm import Session, scoped_session, sessionmaker
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
    OptionsFlowWithReload,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import async_get_hass, callback
from homeassistant.data_entry_flow import section
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import selector

from .const import CONF_ADVANCED_OPTIONS, CONF_COLUMN_NAME, CONF_QUERY, DOMAIN
from .util import (
    EmptyQueryError,
    InvalidSqlQuery,
    MultipleQueryError,
    NotSelectQueryError,
    UnknownQueryTypeError,
    check_and_render_sql_query,
    resolve_db_url,
)

_LOGGER = logging.getLogger(__name__)


OPTIONS_SCHEMA: vol.Schema = vol.Schema(
    {
        vol.Required(CONF_QUERY): selector.TemplateSelector(),
        vol.Required(CONF_COLUMN_NAME): selector.TextSelector(),
        vol.Required(CONF_ADVANCED_OPTIONS): section(
            vol.Schema(
                {
                    vol.Optional(CONF_VALUE_TEMPLATE): selector.TemplateSelector(),
                    vol.Optional(CONF_UNIT_OF_MEASUREMENT): selector.TextSelector(),
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
            ),
            {"collapsed": True},
        ),
    }
)

CONFIG_SCHEMA: vol.Schema = vol.Schema(
    {
        vol.Required(CONF_NAME, default="Select SQL Query"): selector.TextSelector(),
        vol.Optional(CONF_DB_URL): selector.TextSelector(),
    }
)


def validate_sql_select(value: str) -> str:
    """Validate that value is a SQL SELECT query."""
    hass = async_get_hass()
    try:
        return check_and_render_sql_query(hass, value)
    except (TemplateError, InvalidSqlQuery) as err:
        _LOGGER.debug("Invalid query '%s' results in '%s'", value, err.args[0])
        raise


def validate_db_connection(db_url: str) -> bool:
    """Validate db connection."""

    engine: Engine | None = None
    sess: Session | None = None
    try:
        engine = sqlalchemy.create_engine(db_url, future=True)
        sessmaker = scoped_session(sessionmaker(bind=engine, future=True))
        sess = sessmaker()
        sess.execute(sqlalchemy.text("select 1 as value"))
    except SQLAlchemyError as error:
        _LOGGER.debug("Execution error %s", error)
        if sess:
            sess.close()
        if engine:
            engine.dispose()
        raise

    if sess:
        sess.close()
        engine.dispose()

    return True


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
        raise InvalidSqlQuery from error

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

    VERSION = 2

    data: dict[str, Any]

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

        if user_input is not None:
            db_url = user_input.get(CONF_DB_URL)

            try:
                db_url_for_validation = resolve_db_url(self.hass, db_url)
                await self.hass.async_add_executor_job(
                    validate_db_connection, db_url_for_validation
                )
            except SQLAlchemyError:
                errors["db_url"] = "db_url_invalid"

            if not errors:
                self.data = {CONF_NAME: user_input[CONF_NAME]}
                if db_url and db_url_for_validation != get_instance(self.hass).db_url:
                    self.data[CONF_DB_URL] = db_url
                return await self.async_step_options()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(CONFIG_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_options(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        errors = {}
        description_placeholders = {}

        if user_input is not None:
            query = user_input[CONF_QUERY]
            column = user_input[CONF_COLUMN_NAME]

            try:
                query = validate_sql_select(query)
                db_url_for_validation = resolve_db_url(
                    self.hass, self.data.get(CONF_DB_URL)
                )
                await self.hass.async_add_executor_job(
                    validate_query, db_url_for_validation, query, column
                )
            except NoSuchColumnError:
                errors["column"] = "column_invalid"
                description_placeholders = {"column": column}
            except (MultipleResultsFound, MultipleQueryError):
                errors["query"] = "multiple_queries"
            except SQLAlchemyError:
                errors["db_url"] = "db_url_invalid"
            except (NotSelectQueryError, UnknownQueryTypeError):
                errors["query"] = "query_no_read_only"
            except (TemplateError, EmptyQueryError, InvalidSqlQuery) as err:
                _LOGGER.debug("Invalid query: %s", err)
                errors["query"] = "query_invalid"

            mod_advanced_options = {
                k: v
                for k, v in user_input[CONF_ADVANCED_OPTIONS].items()
                if v is not None
            }
            user_input[CONF_ADVANCED_OPTIONS] = mod_advanced_options

            if not errors:
                name = self.data[CONF_NAME]
                self.data.pop(CONF_NAME)
                return self.async_create_entry(
                    title=name,
                    data=self.data,
                    options=user_input,
                )

        return self.async_show_form(
            step_id="options",
            data_schema=self.add_suggested_values_to_schema(OPTIONS_SCHEMA, user_input),
            errors=errors,
            description_placeholders=description_placeholders,
        )


class SQLOptionsFlowHandler(OptionsFlowWithReload):
    """Handle SQL options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage SQL options."""
        errors = {}
        description_placeholders = {}

        if user_input is not None:
            db_url = self.config_entry.data.get(CONF_DB_URL)
            query = user_input[CONF_QUERY]
            column = user_input[CONF_COLUMN_NAME]

            try:
                query = validate_sql_select(query)
                db_url_for_validation = resolve_db_url(self.hass, db_url)
                await self.hass.async_add_executor_job(
                    validate_query, db_url_for_validation, query, column
                )
            except NoSuchColumnError:
                errors["column"] = "column_invalid"
                description_placeholders = {"column": column}
            except (MultipleResultsFound, MultipleQueryError):
                errors["query"] = "multiple_queries"
            except SQLAlchemyError:
                errors["db_url"] = "db_url_invalid"
            except (NotSelectQueryError, UnknownQueryTypeError):
                errors["query"] = "query_no_read_only"
            except (TemplateError, EmptyQueryError, InvalidSqlQuery) as err:
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

                mod_advanced_options = {
                    k: v
                    for k, v in user_input[CONF_ADVANCED_OPTIONS].items()
                    if v is not None
                }
                user_input[CONF_ADVANCED_OPTIONS] = mod_advanced_options

                return self.async_create_entry(
                    data=user_input,
                )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, user_input or self.config_entry.options
            ),
            errors=errors,
            description_placeholders=description_placeholders,
        )
