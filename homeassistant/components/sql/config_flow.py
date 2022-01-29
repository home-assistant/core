"""Adds config flow for SQL integration."""
from __future__ import annotations

import logging
from typing import Any

import sqlalchemy
from sqlalchemy.orm import scoped_session, sessionmaker
import voluptuous as vol

from homeassistant.components.recorder import CONF_DB_URL, DEFAULT_DB_FILE, DEFAULT_URL
from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_UNIT_OF_MEASUREMENT, CONF_VALUE_TEMPLATE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import CONF_COLUMN_NAME, CONF_QUERY, DOMAIN, DB_URL_RE

_LOGGER = logging.getLogger(__name__)


def redact_credentials(data):
    """Redact credentials from string data."""
    return DB_URL_RE.sub("//****:****@", data)


def validate_sql_select(value):
    """Validate that value is a SQL SELECT query."""
    if not value.lstrip().lower().startswith("select"):
        raise vol.Invalid("Only SELECT queries allowed")
    return value


DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_DB_URL): cv.string,
        vol.Required(CONF_COLUMN_NAME): cv.string,
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_QUERY): vol.All(cv.string, validate_sql_select),
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    }
)


class SQLConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Trafikverket Train integration."""

    VERSION = 1

    entry: config_entries.ConfigEntry
    hass: HomeAssistant

    async def validate_db(self, hass: HomeAssistant, db_url: str | None) -> bool:
        """Validate database from user input."""

        if not db_url:
            db_url = DEFAULT_URL.format(
                hass_config_path=hass.config.path(DEFAULT_DB_FILE)
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
            return False
        finally:
            if sess:
                sess.close()
        return True

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
            db_url = user_input[CONF_DB_URL]
            query = user_input[CONF_QUERY]
            column = user_input[CONF_COLUMN_NAME]
            uom = user_input.get(CONF_UNIT_OF_MEASUREMENT)
            value_template = user_input[CONF_VALUE_TEMPLATE]

            name = f"Select {column} SQL query"

            validate = await self.validate_db(self.hass, db_url)

            if validate:
                return self.async_create_entry(
                    title=name,
                    data={
                        "db_url": db_url,
                        "query": query,
                        "column": column,
                        "uom": uom,
                        "value_template": value_template,
                        "name": name,
                    },
                )
            else:
                errors["db_url"] = "db_url_invalid"

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )
