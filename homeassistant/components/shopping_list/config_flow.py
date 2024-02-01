"""Config flow to configure the shopping list integration."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class ShoppingListFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for the shopping list integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        # Check if already configured
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title="Shopping list", data={})

        return self.async_show_form(step_id="user")

    async_step_import = async_step_user

    async def async_step_onboarding(
        self, _: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by onboarding."""
        return await self.async_step_user(user_input={})
