"""Config flow for local_ip."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class SimpleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for local_ip."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user")

        return self.async_create_entry(title=DOMAIN, data=user_input)
