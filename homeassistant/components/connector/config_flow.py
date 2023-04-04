"""Config flow for Connector integration."""
from __future__ import annotations

import logging

from connectorlocal.connectorlocal import ConnectorHub
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
        self.errors = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            self.host = user_input[CONF_HOST].split("&")
            self.key = user_input[CONF_API_KEY]
            return await self.async_step_connect()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=self.errors
        )

    async def async_step_connect(self):
        """Connect to the Connector Hub."""
        await self.async_set_unique_id("ConnectorLocalControlID")
        self._abort_if_unique_id_configured()

        connector = ConnectorHub(ip=self.host, key=self.key)
        connector.start_receive_data()
        if connector.is_connected:
            connector.close_receive_data()
            if await connector.device_list() is None:
                return self.async_abort(reason="device_none")
            return self.async_create_entry(
                title=DEFAULT_HUB_NAME,
                data={CONF_HOST: self.host, CONF_API_KEY: self.key},
            )
        connector.close_receive_data()
        if connector.error_code == 1001:
            return self.async_abort(reason="key_error")
        return self.async_abort(reason="port_error")
