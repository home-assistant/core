"""Config flow for the Thread integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class ThreadConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Thread."""

    VERSION = 1

    async def async_step_import(
        self, import_data: dict[str, str] | None = None
    ) -> FlowResult:
        """Set up by import from async_setup."""
        return self.async_create_entry(title="Thread", data={})
