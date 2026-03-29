"""Repairs for the UniFi Access integration."""

from __future__ import annotations

from typing import cast

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant

from .coordinator import UnifiAccessConfigEntry


class ApiTokenExpiredRepair(RepairsFlow):
    """Handler for fixing an expired API token."""

    _entry: UnifiAccessConfigEntry

    def __init__(self, *, entry: UnifiAccessConfigEntry) -> None:
        """Initialize the repair flow."""
        self._entry = entry
        super().__init__()

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of the fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of the fix flow."""
        if user_input is None:
            return self.async_show_form(
                step_id="confirm",
                data_schema=vol.Schema({}),
            )

        self._entry.async_start_reauth(self.hass)
        return self.async_create_entry(data={})


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if (
        data is not None
        and "entry_id" in data
        and (entry := hass.config_entries.async_get_entry(cast(str, data["entry_id"])))
    ):
        if issue_id == "api_token_expired":
            return ApiTokenExpiredRepair(entry=entry)
    return ConfirmRepairFlow()
