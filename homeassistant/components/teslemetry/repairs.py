"""Repairs for the Teslemetry integration."""

from typing import Any

from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    FlowType,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.config_entries import SOURCE_RECONFIGURE, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import TeslemetryConfigEntry
from .const import (
    ISSUE_TYPE_BLE_KEY_REJECTED,
    SUBENTRY_TYPE_VEHICLE,
    VEHICLE_ISSUE_LEARN_MORE,
)


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


class BluetoothKeyRepairFlow(RepairsFlow):
    """Hand a rejected Bluetooth key over to the vehicle's reconfigure flow."""

    def __init__(self, entry_id: str, subentry_id: str) -> None:
        """Create flow."""
        self._entry_id = entry_id
        self._subentry_id = subentry_id

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Open the vehicle's reconfigure flow to re-approve the key."""
        if user_input is None:
            return self.async_show_form(step_id="confirm")
        result = await self.hass.config_entries.subentries.async_init(
            (self._entry_id, SUBENTRY_TYPE_VEHICLE),
            context={"source": SOURCE_RECONFIGURE, "subentry_id": self._subentry_id},
        )
        if result["type"] is FlowResultType.ABORT:
            return self.async_abort(reason=result["reason"])
        # Aborting keeps the issue open until the reconfigure reloads the entry.
        return self.async_abort(
            reason="reconfigure",
            next_flow=(FlowType.CONFIG_SUBENTRIES_FLOW, result["flow_id"]),
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if (
        data is not None
        and data.get("issue_type") == ISSUE_TYPE_BLE_KEY_REJECTED
        and isinstance(entry_id := data.get("entry_id"), str)
        and isinstance(subentry_id := data.get("subentry_id"), str)
        and (entry := hass.config_entries.async_get_entry(entry_id)) is not None
        and subentry_id in entry.subentries
    ):
        return BluetoothKeyRepairFlow(entry_id, subentry_id)
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
