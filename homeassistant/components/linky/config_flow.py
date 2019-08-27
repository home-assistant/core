"""Config flow to configure the Linky integration."""
import logging

import voluptuous as vol
from pylinky.client import LinkyClient, PyLinkyError

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_TIMEOUT, CONF_USERNAME
from homeassistant.core import callback

from .const import DEFAULT_TIMEOUT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class LinkyFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Linky config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize Linky config flow."""
        self._username = None
        self._password = None
        self._timeout = None

    def _configuration_exists(self, username: str) -> bool:
        """Return True if username exists in configuration."""
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.title == username:
                return True
        return False

    @callback
    def _show_setup_form(self, user_input=None, errors=None):
        """Show the setup form to the user."""

        if user_input is None:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")
                    ): str,
                    vol.Required(
                        CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")
                    ): str,
                }
            ),
            errors=errors or {},
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""

        if user_input is None:
            return self._show_setup_form(user_input, None)

        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]
        self._timeout = user_input.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)

        if self._configuration_exists(self._username):
            errors = {}
            errors[CONF_USERNAME] = "username_exists"
            return self._show_setup_form(user_input, errors)

        client = LinkyClient(self._username, self._password, None, self._timeout)
        try:
            await self.hass.async_add_executor_job(client.login)
            await self.hass.async_add_executor_job(client.fetch_data)
        except PyLinkyError as exp:
            _LOGGER.error(exp)
            errors = {}
            errors["PyLinkyError"] = exp
            return self._show_setup_form(user_input, None)
        finally:
            client.close_session()

        _LOGGER.error("LINKY_CONFIG_FLOW:async_create_entry")
        return self.async_create_entry(
            title=self._username,
            data={
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_TIMEOUT: self._timeout,
            },
        )

    async def async_step_import(self, user_input=None):
        """Import a config entry.

        Only host was required in the yaml file all other fields are optional
        """
        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]
        timeout = user_input.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
        if self._configuration_exists(username):
            return self.async_abort(reason="username_exists")
        return await self.async_step_user(
            {CONF_USERNAME: username, CONF_PASSWORD: password, CONF_TIMEOUT: timeout}
        )
