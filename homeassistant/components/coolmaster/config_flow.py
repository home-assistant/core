"""Config flow to configure Coolmaster."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
import homeassistant.helpers.config_validation as cv

from .const import AVAILABLE_MODES, CONF_SUPPORTED_MODES, DEFAULT_PORT, DOMAIN

MODES_SCHEMA = {vol.Required(mode): bool for mode in AVAILABLE_MODES}
HOST_SCHEMA = {
    vol.Required(CONF_HOST): str,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
}

DATA_SCHEMA = vol.Schema({**HOST_SCHEMA, **MODES_SCHEMA})


class CoolmasterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Coolmaster config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def _async_get_entry(self, data):
        supported_modes = [
            key for (key, value) in data.items() if key in AVAILABLE_MODES and value
        ]
        return self.async_create_entry(
            title=data[CONF_HOST],
            data={
                CONF_HOST: data[CONF_HOST],
                CONF_PORT: data[CONF_PORT],
                CONF_SUPPORTED_MODES: supported_modes,
            },
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            return self._async_get_entry(user_input)

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)
