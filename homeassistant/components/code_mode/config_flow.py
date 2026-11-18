"""Config flow for the Code Mode integration."""

from typing import Any, override

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class CodeModeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Code Mode."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(title="Code Mode", data={})
        return self.async_show_form(step_id="user")
