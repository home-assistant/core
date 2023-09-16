"""Config flow for the Hardkernel integration."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class HardkernelConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hardkernel."""

    VERSION = 1

    async def async_step_system(self, data: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(title="Hardkernel", data={})
