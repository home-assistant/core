"""Config flow for the assist conversation integration."""

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class AssistConversationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the assist conversation integration."""

    async def async_step_import(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the import step."""
        return self.async_create_entry(title="Assist conversation", data={})
