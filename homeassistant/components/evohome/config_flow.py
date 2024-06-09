"""Config flow to configure Evohome integration."""

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class EvoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Evohome."""

    VERSION = 1

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle a flow initiated by configuration file."""

        return self.async_create_entry(title="Evohome", data=import_data)
