"""The repairs integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.integration_platform import (
    async_process_integration_platforms,
)

# pylint: disable-next=unused-import
from homeassistant.helpers.issue_registry import (
    async_delete_issue,
    async_get as async_get_issue_registry,
)

from .const import DOMAIN
from .models import RepairsFlow, RepairsProtocol


class ConfirmRepairFlow(RepairsFlow):
    """Handler for an issue fixing flow without any side effects."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""
        return await (self.async_step_confirm())

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data={})

        issue_registry = async_get_issue_registry(self.hass)
        description_placeholders = None
        if issue := issue_registry.async_get_issue(self.handler, self.issue_id):
            description_placeholders = issue.translation_placeholders

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders=description_placeholders,
        )


class RepairsFlowManager(data_entry_flow.FlowManager):
    """Manage repairs flows."""

    async def async_create_flow(
        self,
        handler_key: Any,
        *,
        context: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> RepairsFlow:
        """Create a flow. platform is a repairs module."""
        assert data and "issue_id" in data
        issue_id = data["issue_id"]

        issue_registry = async_get_issue_registry(self.hass)
        issue = issue_registry.async_get_issue(handler_key, issue_id)
        if issue is None or not issue.is_fixable:
            raise data_entry_flow.UnknownStep

        if "platforms" not in self.hass.data[DOMAIN]:
            await async_process_repairs_platforms(self.hass)

        platforms: dict[str, RepairsProtocol] = self.hass.data[DOMAIN]["platforms"]
        if handler_key not in platforms:
            flow: RepairsFlow = ConfirmRepairFlow()
        else:
            platform = platforms[handler_key]
            flow = await platform.async_create_fix_flow(self.hass, issue_id, issue.data)

        flow.issue_id = issue_id
        flow.data = issue.data
        return flow

    async def async_finish_flow(
        self, flow: data_entry_flow.FlowHandler, result: data_entry_flow.FlowResult
    ) -> data_entry_flow.FlowResult:
        """Complete a fix flow."""
        async_delete_issue(self.hass, flow.handler, flow.init_data["issue_id"])
        if "result" not in result:
            result["result"] = None
        return result


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Initialize repairs."""
    hass.data[DOMAIN]["flow_manager"] = RepairsFlowManager(hass)


async def async_process_repairs_platforms(hass: HomeAssistant) -> None:
    """Start processing repairs platforms."""
    hass.data[DOMAIN]["platforms"] = {}

    await async_process_integration_platforms(hass, DOMAIN, _register_repairs_platform)


async def _register_repairs_platform(
    hass: HomeAssistant, integration_domain: str, platform: RepairsProtocol
) -> None:
    """Register a repairs platform."""
    if not hasattr(platform, "async_create_fix_flow"):
        raise HomeAssistantError(f"Invalid repairs platform {platform}")
    hass.data[DOMAIN]["platforms"][integration_domain] = platform
