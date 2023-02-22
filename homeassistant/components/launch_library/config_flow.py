"""Config flow to configure launch library component."""
from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class LaunchLibraryFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Launch Library component."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        # Check if already configured
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(title="Launch Library", data=user_input)

        return self.async_show_form(step_id="user")
