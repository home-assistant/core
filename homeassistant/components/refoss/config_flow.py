"""ConfigFlow for Refoss."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import FlowResult

from .const import DEFAULT_NAME, DOMAIN


class RefossConfigFlow(ConfigFlow, domain=DOMAIN):
    """RefossConfigFlow for Refoss."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """async_step_user for Refoss."""

        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        return self.async_create_entry(title=DEFAULT_NAME, data={})
