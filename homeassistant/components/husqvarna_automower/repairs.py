"""Repairs implementation for the Husqvarna Automower integration."""

from __future__ import annotations

import logging
from typing import Any, cast

from homeassistant import data_entry_flow
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class WrongScopeRepairFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    _entry: ConfigEntry

    def __init__(self, *, entry: ConfigEntry) -> None:
        """Create flow."""

        self._entry = entry
        super().__init__()

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is None:
            return self.async_show_form(
                step_id="confirm",
            )

        self._entry.async_start_reauth(self.hass)
        return self.async_create_entry(data={})


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, Any],
) -> RepairsFlow:
    """Create flow."""
    entry_id = cast(str, data["entry_id"])
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is not None:
        return WrongScopeRepairFlow(entry=entry)
    return ConfirmRepairFlow()
