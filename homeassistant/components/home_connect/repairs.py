"""Repairs flows for Home Connect."""

from typing import cast

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .coordinator import HomeConnectConfigEntry


class EnableApplianceUpdatesFlow(RepairsFlow):
    """Handler for enabling appliance's updates after being refreshed too many times."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            assert self.data
            entry = self.hass.config_entries.async_get_entry(
                cast(str, self.data["entry_id"])
            )
            assert entry
            entry = cast(HomeConnectConfigEntry, entry)
            await entry.runtime_data.reset_execution_tracker(
                cast(str, self.data["appliance_ha_id"])
            )
            return self.async_create_entry(data={})

        issue_registry = ir.async_get(self.hass)
        description_placeholders = None
        if issue := issue_registry.async_get_issue(self.handler, self.issue_id):
            description_placeholders = issue.translation_placeholders

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders=description_placeholders,
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if issue_id.startswith("home_connect_too_many_connected_paired_events"):
        return EnableApplianceUpdatesFlow()
    return ConfirmRepairFlow()
