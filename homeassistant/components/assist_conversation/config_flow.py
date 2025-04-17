"""Config flow for the assist conversation integration."""

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class onfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the assist conversation integration."""

    async def async_step_system(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the system step."""
        return self.async_create_entry(title="assist conversation", data={})
