"""Repairs for the SeventeenTrack integration."""

from typing import cast

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from . import DOMAIN


@callback
def deprecate_sensor_issue(hass: HomeAssistant, entry_id: str) -> None:
    """Ensure an issue is registered."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        "deprecate_sensor",
        breaks_in_ha_version="2025.1.0",
        issue_domain=DOMAIN,
        is_fixable=True,
        is_persistent=True,
        translation_key="deprecate_sensor",
        severity=ir.IssueSeverity.WARNING,
        data={"entry_id": entry_id},
    )


class SensorDeprecationRepairFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Create flow."""
        super().__init__()
        self.entry = entry

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
            data = {**self.entry.data, "deprecated": True}
            self.hass.config_entries.async_update_entry(self.entry, data=data)
            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if data and (entry_id := cast(str, data.get("entry_id"))):
        entry = hass.config_entries.async_get_entry(entry_id)
        assert entry
        return SensorDeprecationRepairFlow(entry)
    return ConfirmRepairFlow()
