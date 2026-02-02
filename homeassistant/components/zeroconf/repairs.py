"""Repairs for the zeroconf integration."""

from __future__ import annotations

from homeassistant import data_entry_flow
from homeassistant.components.homeassistant import (
    DOMAIN as DOMAIN_HOMEASSISTANT,
    SERVICE_HOMEASSISTANT_RESTART,
)
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import instance_id, issue_registry as ir


class DuplicateInstanceIDRepairFlow(RepairsFlow):
    """Handler for duplicate instance ID repair."""

    @callback
    def _async_get_placeholders(self) -> dict[str, str]:
        issue_registry = ir.async_get(self.hass)
        issue = issue_registry.async_get_issue(self.handler, self.issue_id)
        assert issue is not None
        return issue.translation_placeholders or {}

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the initial step."""
        return await self.async_step_confirm_recreate()

    async def async_step_confirm_recreate(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step."""
        if user_input is not None:
            await instance_id.async_recreate(self.hass)
            await self.hass.services.async_call(
                DOMAIN_HOMEASSISTANT, SERVICE_HOMEASSISTANT_RESTART
            )

            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="confirm_recreate",
            description_placeholders=self._async_get_placeholders(),
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if issue_id == "duplicate_instance_id":
        return DuplicateInstanceIDRepairFlow()

    # If Zeroconf adds confirm-only repairs in the future, this should be changed
    # to return a ConfirmRepairFlow instead of raising a ValueError
    raise ValueError(f"unknown repair {issue_id}")
