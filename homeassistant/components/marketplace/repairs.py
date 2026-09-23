"""Repairs platform for the Marketplace."""

from typing import Any

import voluptuous as vol

from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.core import HomeAssistant

from .base import async_get_store


class RestartRequiredFixFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, issue_id: str) -> None:
        """Initialize the fix flow."""
        self.issue_id = issue_id

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""

        return await self.async_step_confirm_restart()

    async def async_step_confirm_restart(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            await self.hass.services.async_call("homeassistant", "restart")
            return self.async_create_entry(title="", data={})

        store = async_get_store(self.hass)
        integration = store.repositories.get_by_id(self.issue_id.split("_")[2])

        return self.async_show_form(
            step_id="confirm_restart",
            data_schema=vol.Schema({}),
            description_placeholders={
                "name": integration.display_name if integration else ""
            },
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None = None,
    *args: Any,
    **kwargs: Any,
) -> RepairsFlow | None:
    """Create flow."""
    if issue_id.startswith("restart_required"):
        return RestartRequiredFixFlow(issue_id)
    return None
