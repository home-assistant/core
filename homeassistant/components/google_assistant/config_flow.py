"""Config flow for google assistant component."""

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import CONF_PROJECT_ID, DOMAIN


class GoogleAssistantHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a config entry."""
        await self.async_set_unique_id(unique_id=import_data[CONF_PROJECT_ID])
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=import_data[CONF_PROJECT_ID], data=import_data
        )
