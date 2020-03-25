"""Config flow for MyIO Valet Mega integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import callback

from .const import CONF_PORT_APP, CONF_REFRESH_TIME, DEFAULT_REFRESH_TIME, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default="myIO-Server"): str,
        vol.Required(CONF_HOST, default="192.168.1.170"): str,
        vol.Required(CONF_PORT, default="80"): int,
        vol.Required(CONF_PORT_APP, default="843"): int,
        vol.Required(CONF_USERNAME, default="admin"): str,
        vol.Required(CONF_PASSWORD, default="admin"): str,
    }
)


@config_entries.HANDLERS.register(DOMAIN)
class configFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MyIO Valet Mega."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize."""

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        if user_input is not None:
            if any(
                user_input["name"] == entry.data["name"]
                for entry in self._async_current_entries()
            ):
                return self.async_abort(reason="already_configured")

        if not user_input:
            return self._show_form()

        return self.async_create_entry(title=user_input[CONF_NAME], data=user_input,)

    @callback
    def _show_form(self, errors=None):
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors if errors else {},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return MyIOoptionsFlowHandler(config_entry)


class MyIOoptionsFlowHandler(config_entries.OptionsFlow):
    """Handle myIO options."""

    def __init__(self, config_entry):
        """Initialize myIO options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the myIO options."""
        return await self.async_step_myio_options()

    async def async_step_myio_options(self, user_input=None):
        """Manage the device tracker options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_REFRESH_TIME,
                default=self.config_entry.options.get(
                    CONF_REFRESH_TIME, DEFAULT_REFRESH_TIME
                ),
            ): int,
        }
        return self.async_show_form(
            step_id="myio_options", data_schema=vol.Schema(options)
        )
