"""Config flow for Squeezebox Player integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import FlowResult

from .const import DEFAULT_NAME, DOMAIN


class SqueezeboxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Squeezebox Player."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        # we have nothing to configure so simply create the entry
        return self.async_create_entry(title=DEFAULT_NAME, data={})
