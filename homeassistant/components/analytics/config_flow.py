"""Config flow for Analytics integration."""

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class AnalyticsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Analytics."""

    VERSION = 1

    async def async_step_system(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        return self.async_create_entry(title="Analytics", data={})
