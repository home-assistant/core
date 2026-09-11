"""Repairs for the Teslemetry integration."""

from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import TeslemetryConfigEntry
from .const import VEHICLE_ISSUE_LEARN_MORE


class VehicleMetadataRepairFlow(RepairsFlow):
    """Handle a repair that clears once the vehicle metadata issue resolves."""

    def __init__(
        self, entry: TeslemetryConfigEntry, vin: str, issue_type: str, vehicle: str
    ) -> None:
        """Create flow."""
        self.entry = entry
        self.vin = vin
        self.issue_type = issue_type
        self.placeholders = {
            "vehicle": vehicle,
            "link": VEHICLE_ISSUE_LEARN_MORE.get(issue_type) or "",
        }

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            coordinator = self.entry.runtime_data.metadata_coordinator
            await coordinator.async_refresh()
            vehicles = (coordinator.data or {}).get("vehicles", {})
            still_present = vehicles.get(self.vin, {}).get("issue") == self.issue_type
            if coordinator.last_update_success and not still_present:
                return self.async_create_entry(data={})
            return self.async_show_form(
                step_id="confirm",
                description_placeholders=self.placeholders,
                errors={"base": "not_resolved"},
            )

        return self.async_show_form(
            step_id="confirm",
            description_placeholders=self.placeholders,
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if (
        data is not None
        and isinstance(entry_id := data.get("entry_id"), str)
        and isinstance(vin := data.get("vin"), str)
        and isinstance(issue_type := data.get("issue_type"), str)
        and isinstance(vehicle := data.get("vehicle"), str)
        and (entry := hass.config_entries.async_get_entry(entry_id)) is not None
        and entry.state is ConfigEntryState.LOADED
    ):
        return VehicleMetadataRepairFlow(entry, vin, issue_type, vehicle)

    return ConfirmRepairFlow()
