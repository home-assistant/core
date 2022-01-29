"""Adds config flow for SQL integration."""
from __future__ import annotations

import logging
from typing import Any

import sqlalchemy
from sqlalchemy.orm import scoped_session, sessionmaker
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.recorder import CONF_DB_URL, DEFAULT_DB_FILE, DEFAULT_URL
from homeassistant.const import CONF_NAME, CONF_UNIT_OF_MEASUREMENT, CONF_VALUE_TEMPLATE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.template as template_helper

from .const import CONF_COLUMN_NAME, CONF_QUERY, DB_URL_RE, DOMAIN

_LOGGER = logging.getLogger(__name__)


def redact_credentials(data: str) -> str:
    """Redact credentials from string data."""
    return DB_URL_RE.sub("//****:****@", data)


def validate_sql_select(value: str) -> str | None:
    """Validate that value is a SQL SELECT query."""
    if not value.lstrip().lower().startswith("select"):
        return None
    return value


def validate_template(value: str | None) -> template_helper.Template | None:
    """Validate template syntax."""
    template_value = template_helper.Template(str(value))
    try:
        template_value.ensure_valid()
    except TemplateError:
        return None
    return template_value


DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_DB_URL): cv.string,
        vol.Required(CONF_COLUMN_NAME): cv.string,
        vol.Required(CONF_QUERY): cv.string,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.string,
    }
)


class SQLConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SQL integration."""

    VERSION = 1

    entry: config_entries.ConfigEntry
    hass: HomeAssistant

    async def validate_db(self, db_in: str | None) -> str | None:
        """Validate database from user input."""

        if not (db_url := db_in):
            db_url = DEFAULT_URL.format(
                hass_config_path=self.hass.config.path(DEFAULT_DB_FILE)
            )

        sess = None
        try:
            engine = sqlalchemy.create_engine(db_url)
            sessmaker = scoped_session(sessionmaker(bind=engine))

            # Run a dummy query just to test the db_url
            sess = sessmaker()
            sess.execute("SELECT 1;")

        except sqlalchemy.exc.SQLAlchemyError as err:
            _LOGGER.error(
                "Couldn't connect using %s DB_URL: %s",
                redact_credentials(db_url),
                redact_credentials(str(err)),
            )
            return None
        finally:
            if sess:
                sess.close()
        return db_url

    async def async_step_import(self, config: dict[str, Any] | None) -> FlowResult:
        """Import a configuration from config.yaml."""

        self._async_abort_entries_match(config)
        return await self.async_step_user(user_input=config)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step."""
        errors = {}

        if user_input is not None:
            db_in = user_input.get(CONF_DB_URL)
            query = user_input[CONF_QUERY]
            column = user_input[CONF_COLUMN_NAME]
            uom = user_input.get(CONF_UNIT_OF_MEASUREMENT)
            value_template = user_input.get(CONF_VALUE_TEMPLATE)

            name = f"Select {column} SQL query"

            db_url = await self.validate_db(db_in)
            query_syntax = validate_sql_select(query)
            template_syntax = validate_template(value_template)

            if db_url and query_syntax and template_syntax:
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_DB_URL: db_url,
                        CONF_QUERY: query,
                        CONF_COLUMN_NAME: column,
                        CONF_UNIT_OF_MEASUREMENT: uom,
                        CONF_VALUE_TEMPLATE: value_template,
                        CONF_NAME: name,
                    },
                )
            if not db_url:
                errors["db_url"] = "db_url_invalid"
            if not query_syntax:
                errors["query"] = "query_invalid"
            if not template_syntax:
                errors["value_template"] = "value_template_invalid"

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )
