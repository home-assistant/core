"""Repairs platform for the proximity integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant

from . import _get_proximity_entity_usage
from .const import DOMAIN


class ProximityDeprecatedFixFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, issue_id: str) -> None:
        """Initialize."""
        self.issue_id = issue_id
        self.proximity_entity = issue_id.replace("deprecated_proximity_entity_", "")

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        used_in = _get_proximity_entity_usage(
            self.hass, f"{DOMAIN}.{self.proximity_entity}"
        )

        if user_input is not None:
            if used_in:
                return self.async_abort(reason="not_solved")
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={
                "entity": f"{DOMAIN}.{self.proximity_entity}",
                "used_in": "\n- ".join([f"`{x}`" for x in used_in]),
            },
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, Any] | None,
) -> RepairsFlow:
    """Create flow."""
    if issue_id.startswith("deprecated_proximity_entity"):
        return ProximityDeprecatedFixFlow(issue_id)
    return ConfirmRepairFlow()
