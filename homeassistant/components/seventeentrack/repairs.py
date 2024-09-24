"""Repairs for the SeventeenTrack integration."""

import voluptuous as vol

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DEPRECATED_KEY


class SensorDeprecationRepairFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Create flow."""
        self.entry = entry

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            data = {**self.entry.data, DEPRECATED_KEY: True}
            self.hass.config_entries.async_update_entry(self.entry, data=data)
            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
        )


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict
) -> RepairsFlow:
    """Create flow."""
    if issue_id.startswith("deprecate_sensor_"):
        entry = hass.config_entries.async_get_entry(data["entry_id"])
        assert entry
        return SensorDeprecationRepairFlow(entry)
    return ConfirmRepairFlow()
