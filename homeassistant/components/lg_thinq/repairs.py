"""Repairs for LG ThinQ integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


class DeprecatedFanSpeedRepairFlow(RepairsFlow):
    """Handler for deprecated fan speed number entity fixing flow."""

    def __init__(self, data: dict[str, str]) -> None:
        """Initialize."""
        self.entity_id = data["entity_id"]
        self._placeholders = data

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
            er.async_get(self.hass).async_update_entity(
                self.entity_id,
                disabled_by=er.RegistryEntryDisabler.USER,
            )
            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders=self._placeholders,
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str],
) -> RepairsFlow:
    """Create flow."""
    if issue_id.startswith("deprecated_fan_speed_number_"):
        return DeprecatedFanSpeedRepairFlow(data)
    return ConfirmRepairFlow()
