"""Repairs platform for the Marketplace."""

from typing import Any

import probatio

from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.core import HomeAssistant

from .base import async_get_marketplace
from .critical import CRITICAL_ISSUE_PREFIX, async_acknowledge_critical_repository


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

        marketplace = async_get_marketplace(self.hass)
        integration = marketplace.repositories.get_by_id(self.issue_id.split("_")[2])

        return self.async_show_form(
            step_id="confirm_restart",
            data_schema=probatio.Schema({}),
            description_placeholders={
                "name": integration.display_name if integration else ""
            },
        )


class CriticalRepositoryFixFlow(RepairsFlow):
    """Confirm the removal of a repository the catalog marks as critical."""

    def __init__(self, repository: str, reason: str) -> None:
        """Initialize the fix flow."""
        self.repository = repository
        self.reason = reason

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Show why the repository was removed, until the user confirms."""
        if user_input is not None:
            await async_acknowledge_critical_repository(self.hass, self.repository)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="confirm",
            data_schema=probatio.Schema({}),
            description_placeholders={
                "repository": self.repository,
                "reason": self.reason,
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
    if issue_id.startswith(CRITICAL_ISSUE_PREFIX) and data:
        return CriticalRepositoryFixFlow(str(data["repository"]), str(data["reason"]))
    return None
