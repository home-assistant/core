"""Config flow for Connector integration."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_HOST

from .const import DEFAULT_HUB_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_API_KEY): vol.All(str, vol.Length(min=16, max=16)),
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Connector."""

    VERSION = 1

    CONNECTION_CLASS = config_entries.CONN_CLASS_UNKNOWN

    def __init__(self):
        """Initialize the connector hub."""
        self.host = None
        self.key = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            self.host = user_input[CONF_HOST].split("&")
            self.key = user_input[CONF_API_KEY]
            # _LOGGER.info("host:", self.host)
            # _LOGGER.info("key:", self.key)
            return await self.async_step_connect()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_connect(self, user_input=None):
        """Connect to the Connector Hub."""
        await self.async_set_unique_id("ConnectorLocalControlID")
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=DEFAULT_HUB_NAME,
            data={CONF_HOST: self.host, CONF_API_KEY: self.key},
        )
