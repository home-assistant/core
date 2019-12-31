"""Config flow for local_ip."""
import voluptuous as vol

from homeassistant import config_entries

from . import DOMAIN


class SimpleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for local_ip."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            if any(
                user_input["name"] == entry.data["name"]
                for entry in self._async_current_entries()
            ):
                return self.async_abort(reason="already_configured")

            return self.async_create_entry(title=user_input["name"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("name", default=DOMAIN): str}),
            errors={},
        )

    async def async_step_import(self, import_info):
        """Handle import from config file."""
        return await self.async_step_user(import_info)
