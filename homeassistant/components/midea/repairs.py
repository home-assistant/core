"""Repairs for Midea devices."""

from typing import Any, cast, override

from midealocal.devices.ac import MideaACDevice

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlowResult
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN


class FullDustRepairFlow(ConfirmRepairFlow):
    """Reset the filter reminder after the filter has been cleaned."""

    def __init__(self, entry_id: str) -> None:
        """Initialize the repair flow."""
        self.entry_id = entry_id

    @override
    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Reset the device filter reminder after confirmation."""
        if user_input is not None:
            entry = self.hass.config_entries.async_get_entry(self.entry_id)
            if entry is None:
                return self.async_abort(reason="entry_removed")
            device = cast("MideaACDevice", entry.runtime_data)
            await self.hass.async_add_executor_job(device.reset_filter)
            return self.async_abort(reason="reset_requested")
        return await super().async_step_confirm(user_input)


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> FullDustRepairFlow:
    """Create a flow to reset an AC filter reminder."""
    assert data is not None
    return FullDustRepairFlow(str(data["entry_id"]))


@callback
def async_sync_full_dust_issue(
    hass: HomeAssistant,
    entry_id: str,
    full_dust: Any,
) -> None:
    """Create or clear the filter repair issue from the reported state."""
    issue_id = f"full_dust_{entry_id}"
    if full_dust is True:
        ir.async_create_issue(
            hass=hass,
            domain=DOMAIN,
            issue_id=issue_id,
            is_fixable=True,
            is_persistent=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="full_dust",
            data={"entry_id": entry_id},
        )
    elif full_dust is False:
        ir.async_delete_issue(hass=hass, domain=DOMAIN, issue_id=issue_id)
