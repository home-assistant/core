"""PJLink config flow."""
from __future__ import annotations

from typing import Any

from homeassistant import config_entries, data_entry_flow

from .const import CONFIG_ENTRY_SCHEMA, DOMAIN, INTEGRATION_NAME


class PJLinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """PJLink config flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Create a user-configured PJLink device."""
        if user_input is not None:
            return self.async_create_entry(title=INTEGRATION_NAME, data=user_input)

        return self.async_show_form(step_id="user", data_schema=CONFIG_ENTRY_SCHEMA)
