"""Config flow for Profiler integration."""
import voluptuous as vol

from homeassistant import config_entries

from .const import DEFAULT_NAME
from .const import DOMAIN  # pylint: disable=unused-import


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Profiler."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_UNKNOWN

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(title=DEFAULT_NAME, data={})

        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))
