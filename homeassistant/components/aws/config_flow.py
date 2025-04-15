"""Config flow for AWS component."""

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class AWSFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a config entry."""
        return self.async_create_entry(title="configuration.yaml", data=import_data)
