"""Config flow for google assistant component."""

from homeassistant import config_entries

from .const import CONF_PROJECT_ID, DOMAIN


class GoogleAssistantHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def async_step_import(self, user_input):
        """Import a config entry."""
        await self.async_set_unique_id(unique_id=user_input[CONF_PROJECT_ID])
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=user_input[CONF_PROJECT_ID], data=user_input
        )
