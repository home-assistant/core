"""Adds config flow for SQL integration."""
from __future__ import annotations

import logging
from typing import Any

import sqlalchemy
from sqlalchemy.engine import Result
from sqlalchemy.exc import NoSuchColumnError, SQLAlchemyError
from sqlalchemy.orm import Session, scoped_session, sessionmaker
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.recorder import CONF_DB_URL
from homeassistant.const import CONF_NAME, CONF_UNIT_OF_MEASUREMENT, CONF_VALUE_TEMPLATE
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
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
    }
)

CONFIG_SCHEMA: vol.Schema = vol.Schema(
    {
        vol.Required(CONF_NAME, default="Select SQL Query"): selector.TextSelector(),
    }
).extend(OPTIONS_SCHEMA.schema)


def validate_sql_select(value: str) -> str | None:
    """Validate that value is a SQL SELECT query."""
    if not value.lstrip().lower().startswith("select"):
        raise ValueError("Incorrect Query")
    return value


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


class SQLConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SQL integration."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SQLOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SQLOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step."""
        errors = {}
        description_placeholders = {}

        if user_input is not None:
            db_url = user_input.get(CONF_DB_URL)
            query = user_input[CONF_QUERY]
            column = user_input[CONF_COLUMN_NAME]
            uom = user_input.get(CONF_UNIT_OF_MEASUREMENT)
            value_template = user_input.get(CONF_VALUE_TEMPLATE)
            name = user_input[CONF_NAME]
            db_url_for_validation = None

            try:
                validate_sql_select(query)
                db_url_for_validation = resolve_db_url(self.hass, db_url)
                await self.hass.async_add_executor_job(
                    validate_query, db_url_for_validation, query, column
                )
            except NoSuchColumnError:
                errors["column"] = "column_invalid"
                description_placeholders = {"column": column}
            except SQLAlchemyError:
                errors["db_url"] = "db_url_invalid"
            except ValueError:
                errors["query"] = "query_invalid"

            add_db_url = (
                {CONF_DB_URL: db_url} if db_url == db_url_for_validation else {}
            )

            if not errors:
                return self.async_create_entry(
                    title=name,
                    data={},
                    options={
                        **add_db_url,
                        CONF_QUERY: query,
                        CONF_COLUMN_NAME: column,
                        CONF_UNIT_OF_MEASUREMENT: uom,
                        CONF_VALUE_TEMPLATE: value_template,
                        CONF_NAME: name,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(CONFIG_SCHEMA, user_input),
            errors=errors,
            description_placeholders=description_placeholders,
        )


class SQLOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle SQL options."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        """Initialize SQL options flow."""
        self.entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage SQL options."""
        errors = {}
        description_placeholders = {}

        if user_input is not None:
            db_url = user_input.get(CONF_DB_URL)
            query = user_input[CONF_QUERY]
            column = user_input[CONF_COLUMN_NAME]
            name = self.entry.options.get(CONF_NAME, self.entry.title)

            try:
                validate_sql_select(query)
                db_url_for_validation = resolve_db_url(self.hass, db_url)
                await self.hass.async_add_executor_job(
                    validate_query, db_url_for_validation, query, column
                )
            except NoSuchColumnError:
                errors["column"] = "column_invalid"
                description_placeholders = {"column": column}
            except SQLAlchemyError:
                errors["db_url"] = "db_url_invalid"
            except ValueError:
                errors["query"] = "query_invalid"
            else:
                new_user_input = user_input
                if new_user_input.get(CONF_DB_URL) and db_url == db_url_for_validation:
                    new_user_input.pop(CONF_DB_URL)
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_NAME: name,
                        **new_user_input,
                    },
                )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, user_input or self.entry.options
            ),
            errors=errors,
            description_placeholders=description_placeholders,
        )
