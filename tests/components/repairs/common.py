"""Common classes for repairs tests."""

from typing import Any

import probatio

from homeassistant.components.repairs import (
    FlowType,
    RepairsFlow,
    RepairsFlowResult,
    repairs_flow_manager,
)
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.issue_registry as ir


class MockFixFlowNextFlowRepairsFlow(RepairsFlow):
    """Mock RepairsFlow for testing repairs flow that continue in other repairs flows."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None
    ) -> RepairsFlowResult:
        """Start a flow."""
        return await self.async_step_confirm(None)

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None
    ) -> RepairsFlowResult:
        """Complete the mock repairs flow."""
        if user_input is not None:
            repairs = repairs_flow_manager(self.hass)
            next_flow = await repairs.async_init(
                "fake_integration", context={"issue_id": "issue_1"}
            )
            if "remove_issue" in user_input:
                ir.async_delete_issue(self.hass, "fake_integration", "issue_1")
            return self.async_create_entry(
                data={}, next_flow=(FlowType.REPAIRS_FLOW, next_flow["flow_id"])
            )
        return self.async_show_form(
            step_id="confirm",
            data_schema=probatio.Schema(
                {probatio.Optional("remove_issue"): cv.boolean}
            ),
        )
