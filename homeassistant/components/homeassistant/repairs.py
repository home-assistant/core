"""Repairs for Home Assistant."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult


class IntegrationNotFoundFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, data: dict[str, str]) -> None:
        """Initialize."""
        self.domain = data["domain"]
        self.description_placeholders: dict[str, str] = data

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_remove_entries()

    async def async_step_remove_entries(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the remove entries step of a fix flow."""
        if user_input is not None:
            entries = self.hass.config_entries.async_entries(self.domain)
            for entry in entries:
                await self.hass.config_entries.async_remove(entry.entry_id)
            return self.async_create_entry(data={})
        return self.async_show_form(
            step_id="remove_entries",
            data_schema=vol.Schema({}),
            description_placeholders=self.description_placeholders,
        )


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, str] | None
) -> RepairsFlow:
    """Create flow."""

    if issue_id.split(".")[0] == "integration_not_found":
        assert data
        return IntegrationNotFoundFlow(data)
    return ConfirmRepairFlow()
