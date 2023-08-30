"""Config flow for the Cloud integration."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class CloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Cloud integration."""

    VERSION = 1

    async def async_step_system(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the system step."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Cloud", data={})
