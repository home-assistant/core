"""Config flow for Speedtest.net."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_MONITORED_CONDITIONS, CONF_SCAN_INTERVAL
from homeassistant.core import callback

from . import server_id_valid
from .const import (
    CONF_MANUAL,
    CONF_SERVER_ID,
    CONF_SERVER_NAME,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SERVER,
    DOMAIN,
)


class SpeedTestFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Speedtest.net config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return SpeedTestOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is None:
            return self.async_show_form(step_id="user")

        return self.async_create_entry(title=DEFAULT_NAME, data=user_input)

    async def async_step_import(self, import_config):
        """Import from config."""
        if (
            CONF_SERVER_ID in import_config
            and not await self.hass.async_add_executor_job(
                server_id_valid, import_config[CONF_SERVER_ID]
            )
        ):
            return self.async_abort(reason="wrong_server_id")

        import_config[CONF_SCAN_INTERVAL] = int(
            import_config[CONF_SCAN_INTERVAL].total_seconds() / 60
        )
        import_config.pop(CONF_MONITORED_CONDITIONS)

        return await self.async_step_user(user_input=import_config)


class SpeedTestOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle SpeedTest options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry
        self._servers = {}

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        errors = {}

        if user_input is not None:
            server_name = user_input[CONF_SERVER_NAME]
            if server_name != "*Auto Detect":
                server_id = self._servers[server_name]["id"]
                user_input[CONF_SERVER_ID] = server_id
            else:
                user_input[CONF_SERVER_ID] = None

            return self.async_create_entry(title="", data=user_input)

        self._servers = self.hass.data[DOMAIN].servers

        server = []
        if self.config_entry.options.get(
            CONF_SERVER_ID
        ) and not self.config_entry.options.get(CONF_SERVER_NAME):
            server = [
                key
                for (key, value) in self._servers.items()
                if value.get("id") == self.config_entry.options[CONF_SERVER_ID]
            ]
        server_name = server[0] if server else DEFAULT_SERVER

        options = {
            vol.Optional(
                CONF_SERVER_NAME,
                default=self.config_entry.options.get(CONF_SERVER_NAME, server_name),
            ): vol.In(self._servers.keys()),
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
