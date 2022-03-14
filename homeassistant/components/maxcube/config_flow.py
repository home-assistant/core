"""Adds config flow for maxcube."""
from maxcube.cube import MaxCube
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.data_entry_flow import FlowResult
from homeassistant.util.dt import now

from . import DOMAIN


@config_entries.HANDLERS.register(DOMAIN)
class MaxCubeFlowHandler(config_entries.ConfigFlow):
    """Config flow for MaxCube."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize."""
        self._errors = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        if user_input is not None:
            host = user_input.get(CONF_HOST)
            port = user_input.get(CONF_PORT, 62910)

            try:
                cube = MaxCube(host, port, now=now)
                cube.disconnect()
            except Exception:  # pylint: disable=broad-except
                return self.async_abort(reason="connection_error")

            return self.async_create_entry(title=f"{host}:{port}", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PORT, default=62910): int,
                    vol.Optional(CONF_SCAN_INTERVAL, default=300): int,
                }
            ),
            errors=self._errors,
        )

    async def async_step_import(self, import_config) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        self._async_abort_entries_match(
            {
                CONF_HOST: import_config.get(CONF_HOST),
                CONF_PORT: import_config.get(CONF_PORT),
            }
        )

        return await self.async_step_user(user_input=import_config)
