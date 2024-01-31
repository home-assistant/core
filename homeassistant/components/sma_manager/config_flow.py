"""SMA Manager Config Flow for UI configuration."""


import logging
import re
from sma_manager_api import SMA
from voluptuous import Required, Schema
from homeassistant import config_entries
from .const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_REFRESH_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class SMAManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SMA Manager."""

    VERSION = 1

    def __init__(self):
        """Init Config Flow object with data default values."""
        self._data = {
            CONF_NAME: "SMA Manager",
            CONF_HOST: "239.12.255.254",
            CONF_PORT: 9522,
            CONF_REFRESH_INTERVAL: 10,
        }

    def _get_schema(self) -> Schema:
        """Generate a schema from data."""

        return Schema(
            {
                Required(CONF_NAME, default=self._data[CONF_NAME]): str,
                Required(CONF_HOST, default=self._data[CONF_HOST]): str,
                Required(CONF_PORT, default=self._data[CONF_PORT]): int,
                Required(
                    CONF_REFRESH_INTERVAL, default=self._data[CONF_REFRESH_INTERVAL]
                ): int,
            }
        )

    async def async_step_user(self, user_input=None):
        """Handle the user step."""
        errors = {}
        if not user_input:
            return self.async_show_form(
                step_id="user", data_schema=self._get_schema(), errors=errors
            )

        # Make user inputted data persistent
        self._data[CONF_NAME] = user_input[CONF_NAME]
        self._data[CONF_HOST] = user_input[CONF_HOST]
        self._data[CONF_PORT] = user_input[CONF_PORT]
        self._data[CONF_REFRESH_INTERVAL] = user_input[CONF_REFRESH_INTERVAL]

        # Validate Multicast IP
        if not re.match(r"\A\d{2,3}.\d{2,3}.\d{2,3}.\d{2,3}$", user_input[CONF_HOST]):
            errors["ip"] = "invalid_id"

        if errors:
            return self.async_show_form(
                step_id="user", data_schema=self._get_schema(), errors=errors
            )

        # Test the connection
        try:
            sma = SMA(
                user_input[CONF_NAME],
                user_input[CONF_HOST],
                user_input[CONF_PORT],
                user_input[CONF_REFRESH_INTERVAL],
            )
        except TimeoutError:
            errors["cannot_connect"] = "cannot_connect"

        if errors:
            return self.async_show_form(
                step_id="user", data_schema=self._get_schema(), errors=errors
            )

        # Check if not integrated already
        await self.async_set_unique_id(sma.serial_number)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)
