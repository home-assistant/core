"""Repairs for Xbox integration."""

from typing import cast

import probatio

from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.issue_registry import async_delete_issue

from .const import DOMAIN


class DeprecatedEntityRepairFlow(RepairsFlow):
    """Handler for a deprecated entity issue fixing flow."""

    def __init__(
        self, issue_id: str, data: dict[str, str | int | float | None]
    ) -> None:
        """Initialize."""
        self._data = data
        self._issue_id = issue_id

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
            er.async_get(self.hass).async_remove(cast(str, self._data["entity_id"]))
            async_delete_issue(self.hass, DOMAIN, self._issue_id)
            return self.async_create_entry(data={})

        return self.async_show_form(step_id="confirm", data_schema=probatio.Schema({}))


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, str | int | float | None] | None
) -> RepairsFlow:
    """Create flow."""
    if not data or "entity_id" not in data:
        raise ValueError("Missing data for repair flow")
    return (
        DeprecatedEntityRepairFlow(issue_id, data)
        if issue_id.startswith("deprecated_entity_")
        else ConfirmRepairFlow()
    )
