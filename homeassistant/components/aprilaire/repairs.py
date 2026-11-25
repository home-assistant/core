"""Repairs for the Aprilaire integration."""

from typing import TYPE_CHECKING

from homeassistant.components.repairs import FlowType, RepairsFlow, RepairsFlowResult
from homeassistant.config_entries import SOURCE_RECONFIGURE
from homeassistant.core import HomeAssistant

from .const import DOMAIN


class WrongDeviceRepairFlow(RepairsFlow):
    """Continue to the reconfigure flow to set the host of the thermostat."""

    def __init__(self, entry_id: str) -> None:
        """Initialize the flow."""
        self._entry_id = entry_id

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of the fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Start the reconfigure flow once the user confirms."""
        if user_input is None:
            return self.async_show_form(step_id="confirm")
        result = await self.hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_RECONFIGURE, "entry_id": self._entry_id}
        )
        return self.async_create_entry(
            data={}, next_flow=(FlowType.CONFIG_FLOW, result["flow_id"])
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create the flow to fix an issue."""
    if TYPE_CHECKING:
        assert data is not None
    return WrongDeviceRepairFlow(str(data["entry_id"]))
