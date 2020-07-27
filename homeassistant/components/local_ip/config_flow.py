"""Config flow for local_ip."""

from homeassistant import config_entries

from .const import DOMAIN


class SimpleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for local_ip."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is None:
            return self.async_show_form(step_id="user")

        return self.async_create_entry(title=DOMAIN, data=user_input)

    async def async_step_import(self, import_info):
        """Handle import from config file."""
        return await self.async_step_user(import_info)
