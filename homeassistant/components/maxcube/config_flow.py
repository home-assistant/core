"""Adds config flow for maxcube."""
import voluptuous as vol

from homeassistant import config_entries

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
            return self.async_create_entry(title="eQ3 MAX!", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("host"): str,
                    vol.Optional("port", default=62910): int,
                    vol.Optional("scan_interval", default=300): int,
                }
            ),
            errors=self._errors,
        )
