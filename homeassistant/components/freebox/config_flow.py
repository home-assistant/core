"""Config flow to configure the Freebox integration."""
import logging

from aiofreepybox import Freepybox
from aiofreepybox.exceptions import HttpRequestError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import API_VERSION, APP_DESC, CONFIG_FILE, DOMAIN

_LOGGER = logging.getLogger(__name__)


class FreeboxFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize Freebox config flow."""

    def _configuration_exists(self, host: str) -> bool:
        """Return True if host exists in configuration."""
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data[CONF_HOST] == host:
                return True
        return False

    def _show_setup_form(self, user_input=None, errors=None):
        """Show the setup form to the user."""

        if user_input is None:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
                    vol.Required(CONF_PORT, default=user_input.get(CONF_PORT, "")): int,
                }
            ),
            errors=errors or {},
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is None:
            return self._show_setup_form(user_input, None)

        host = user_input[CONF_HOST]
        port = user_input[CONF_PORT]

        if self._configuration_exists(host):
            errors["base"] = "already_configured"
            return self._show_setup_form(user_input, errors)

        token_file = self.hass.config.path(CONFIG_FILE)

        fbx = Freepybox(APP_DESC, token_file, API_VERSION)

        try:
            await fbx.open(host, port)
        except HttpRequestError:
            _LOGGER.exception("Failed to connect to Freebox")
            errors["base"] = "connection_failed"
            return self._show_setup_form(user_input, errors)

        return self.async_create_entry(
            title=host, data={CONF_HOST: host, CONF_PORT: port},
        )

    async def async_step_import(self, user_input=None):
        """Import a config entry."""
        if self._configuration_exists(user_input[CONF_HOST]):
            return self.async_abort(reason="already_configured")

        return await self.async_step_user(user_input)
