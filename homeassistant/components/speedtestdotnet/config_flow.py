"""Config flow for Transmission Bittorent Client."""
import speedtest
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import callback

from .const import (
    CONF_MANUAL,
    CONF_SERVER_ID,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)


class SpeedTestFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle SpeedTest config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return SpeedTestOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason="one_instance_allowed")
        if user_input is None:
            user_input = {}
        return self.async_create_entry(title=DEFAULT_NAME, data=user_input)

    async def async_step_import(self, import_config):
        """Import from Transmission client config."""
        import_config[CONF_SCAN_INTERVAL] = (
            import_config[CONF_SCAN_INTERVAL].seconds / 60
        )
        if import_config[CONF_SCAN_INTERVAL] < 1:
            import_config[CONF_SCAN_INTERVAL] = 1

        return await self.async_step_user(user_input=import_config)


class SpeedTestOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Transmission client options."""

    def __init__(self, config_entry):
        """Initialize Transmission options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the Transmission options."""
        errors = {}
        if user_input is not None:

            try:
                api = speedtest.Speedtest()
                api.get_servers([user_input[CONF_SERVER_ID]])
                return self.async_create_entry(title="", data=user_input)
            except speedtest.NoMatchedServers:
                errors[CONF_SERVER_ID] = "wrong_serverid"

        options = {
            vol.Optional(
                CONF_SERVER_ID,
                default=self.config_entry.options.get(CONF_SERVER_ID, ""),
            ): int,
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=self.config_entry.options.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                ),
            ): int,
            vol.Optional(
                CONF_MANUAL, default=self.config_entry.options.get(CONF_MANUAL, False)
            ): bool,
        }

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(options), errors=errors
        )
