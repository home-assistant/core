"""Config flow for the Debug console integration."""

from typing import Any, override

import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN

CONF_ACCEPT_RISKS = "accept_risks"


class DebugConsoleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Debug console."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm enabling the debug console, after warning about the risks."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_ACCEPT_RISKS]:
                return self.async_create_entry(title="Debug console", data={})

            errors[CONF_ACCEPT_RISKS] = "risks_not_accepted"

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {probatio.Required(CONF_ACCEPT_RISKS, default=False): bool}
            ),
            errors=errors,
        )

    async def async_step_system(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enable the debug console by default, on development versions."""
        return self.async_create_entry(title="Debug console", data={})
