"""Repairs for LIFX."""

from typing import override

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlowResult
from homeassistant.core import HomeAssistant


class InvalidSerialRepairFlow(ConfirmRepairFlow):
    """Remove an entry whose serial cannot be migrated."""

    def __init__(self, entry_id: str) -> None:
        """Initialize the flow."""
        self.entry_id = entry_id

    @override
    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Remove the entry once the user confirms."""
        if user_input is not None:
            await self.hass.config_entries.async_remove(self.entry_id)
        return await super().async_step_confirm(user_input)


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> InvalidSerialRepairFlow:
    """Create a fix flow for an invalid serial issue."""
    assert data is not None
    return InvalidSerialRepairFlow(str(data["entry_id"]))
