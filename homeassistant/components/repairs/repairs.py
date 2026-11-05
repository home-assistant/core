"""Fix flow for the update report issue."""

from typing import override

from homeassistant.core import HomeAssistant

from .const import DATA_UPDATE_REPORT
from .issue_handler import ConfirmRepairFlow
from .models import RepairsFlow, RepairsFlowResult


class UpdateReportRepairFlow(ConfirmRepairFlow):
    """Dismiss the update report when confirmed."""

    @override
    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            await self.hass.data[DATA_UPDATE_REPORT].async_dismiss()
        return await super().async_step_confirm(user_input)


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create the flow to dismiss the update report."""
    return UpdateReportRepairFlow()
