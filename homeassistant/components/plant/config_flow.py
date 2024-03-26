"""Config flow to configure the Plant Monitor integration."""
from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from . import PLANT_SCHEMA
from .const import DOMAIN


class PlantFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a plant config flow."""

    VERSION = 1

    @callback
    def _show_form(self, errors: dict[str, str] | None = None) -> FlowResult:
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=PLANT_SCHEMA,
            errors=errors or {},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the start of the config flow."""
        if user_input is None:
            return self._show_form()

        return self.async_create_entry(title="plant", data=user_input)
