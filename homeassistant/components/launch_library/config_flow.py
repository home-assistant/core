"""Config flow to configure launch library component."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class LaunchLibraryFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Launch Library component."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            return self.async_create_entry(title="Launch Library", data=user_input)

        return self.async_show_form(step_id="user")
