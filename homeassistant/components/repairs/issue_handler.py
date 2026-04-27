"""The repairs integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlowResult,
    SubentryFlowResult,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, PlatformNotReady
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.frame import report_usage
from homeassistant.helpers.integration_platform import (
    async_process_integration_platforms,
)

from .const import DOMAIN, FlowType
from .models import RepairsProtocol


class RepairsFlowContext(data_entry_flow.FlowContext, total=False):
    """Typed context dict for repair flow."""

    issue_id: str


class RepairsFlowResult(
    data_entry_flow.FlowResult[RepairsFlowContext, str],
    total=False,
):
    """Typed context dict for repairs flow."""

    next_flow: tuple[FlowType, str]
    # Frontend needs these to render the dialog:
    result: ConfigEntry | ir.IssueEntry


class RepairsFlow(
    data_entry_flow.FlowHandler[RepairsFlowContext, RepairsFlowResult, str]
):
    """Handle a flow for fixing an issue."""

    data: dict[str, str | int | float | None] | None

    @property
    def issue_id(self) -> str:
        """Return the issue ID."""
        return self.context["issue_id"]

    @callback
    def async_create_entry(
        self,
        *,
        title: str | None = None,
        data: Mapping[str, Any],
        description: str | None = None,
        description_placeholders: Mapping[str, str] | None = None,
        next_flow: tuple[FlowType, str] | None = None,
    ) -> RepairsFlowResult:
        """Finish a repair flow."""
        result: RepairsFlowResult = super().async_create_entry(
            title=title,
            data=data,
            description=description,
            description_placeholders=description_placeholders,
        )

        self._async_set_next_flow_if_valid(result, next_flow)

        return result

    @callback
    def async_abort(
        self,
        *,
        reason: str,
        description_placeholders: Mapping[str, str] | None = None,
        next_flow: tuple[FlowType, str] | None = None,
    ) -> RepairsFlowResult:
        """Abort the flow."""
        result: RepairsFlowResult = super().async_abort(
            reason=reason, description_placeholders=description_placeholders
        )

        self._async_set_next_flow_if_valid(result, next_flow)

        return result

    def _async_set_next_flow_if_valid(
        self,
        result: RepairsFlowResult,
        next_flow: tuple[FlowType, str] | None,
    ) -> None:
        """Validate and set next_flow in result if provided."""
        if next_flow is None:
            return
        flow_type, flow_id = next_flow
        if flow_type not in FlowType:
            raise data_entry_flow.FlowError("Invalid next_flow type")
        flow: ConfigFlowResult | SubentryFlowResult | RepairsFlowResult
        entry_id: str | None = None
        if flow_type == FlowType.CONFIG_FLOW:
            flow = self.hass.config_entries.flow.async_get(flow_id)
            entry_id = flow["context"]["entry_id"]
        elif flow_type == FlowType.CONFIG_SUBENTRIES_FLOW:
            flow = self.hass.config_entries.subentries.async_get(flow_id)
            entry_id, _ = flow["handler"]
        elif flow_type == FlowType.OPTIONS_FLOW:
            flow = self.hass.config_entries.options.async_get(flow_id)
            entry_id = flow["handler"]
        else:  # FlowType.REPAIRS_FLOW
            flow = async_get(self.hass).async_get(flow_id)
            issue_registry: ir.IssueRegistry = ir.async_get(self.hass)
            if issue := issue_registry.async_get_issue(
                flow["handler"], flow["context"]["issue_id"]
            ):
                result["result"] = issue
                result["next_flow"] = next_flow
            return
        if entry_id is not None:
            result["result"] = self.hass.config_entries.async_get_known_entry(entry_id)
            result["next_flow"] = next_flow


def repairs_flow_manager(hass: HomeAssistant) -> RepairsFlowManager | None:
    """Get the repairs flow manager."""
    if (domain_data := hass.data.get(DOMAIN)) is None:
        return None
    flow_manager: RepairsFlowManager | None = domain_data.get("flow_manager")
    return flow_manager


def async_get(hass: HomeAssistant) -> RepairsFlowManager:
    """Get the repairs flow manager.

    Preferred over repairs_flow_manager.
    """
    if (flow_manager := repairs_flow_manager(hass)) is None:
        raise PlatformNotReady("Repairs platform not loaded")
    return flow_manager


class ConfirmRepairFlow(RepairsFlow):
    """Handler for an issue fixing flow without any side effects."""

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
            return self.async_create_entry(data={})

        issue_registry = ir.async_get(self.hass)
        description_placeholders = None
        if issue := issue_registry.async_get_issue(self.handler, self.issue_id):
            description_placeholders = issue.translation_placeholders

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders=description_placeholders,
        )


class RepairsFlowManager(
    data_entry_flow.FlowManager[RepairsFlowContext, RepairsFlowResult, str]
):
    """Manage repairs flows."""

    _flow_result = RepairsFlowResult

    async def async_create_flow(
        self,
        handler_key: str,
        *,
        context: RepairsFlowContext | None = None,
        data: dict[str, Any] | None = None,
    ) -> RepairsFlow:
        """Create a flow. platform is a repairs module."""
        context = context or {}
        if "issue_id" not in context:
            assert data and "issue_id" in data
            context["issue_id"] = data["issue_id"]
            report_usage(
                'Created a repair flow using data={"issue_id": issue_id} '
                'instead of context={"issue_id": issue_id}',
                integration_domain=handler_key,
            )
        assert context["issue_id"]

        issue_registry = ir.async_get(self.hass)
        issue = issue_registry.async_get_issue(handler_key, context["issue_id"])
        if issue is None or not issue.is_fixable:
            raise data_entry_flow.UnknownStep("Issue not found in registry")

        if "platforms" not in self.hass.data[DOMAIN]:
            await async_process_repairs_platforms(self.hass)

        platforms: dict[str, RepairsProtocol] = self.hass.data[DOMAIN]["platforms"]
        if handler_key not in platforms:
            flow: RepairsFlow = ConfirmRepairFlow()
        else:
            platform = platforms[handler_key]
            flow = await platform.async_create_fix_flow(
                self.hass, context["issue_id"], issue.data
            )

        flow.context = context
        flow.handler = handler_key
        flow.data = issue.data
        return flow

    async def async_finish_flow(
        self,
        flow: data_entry_flow.FlowHandler[RepairsFlowContext, RepairsFlowResult, str],
        result: RepairsFlowResult,
    ) -> RepairsFlowResult:
        """Complete a fix flow.

        This method is called when a flow step returns FlowResultType.ABORT or
        FlowResultType.CREATE_ENTRY.
        """
        if result.get("type") != data_entry_flow.FlowResultType.ABORT:
            ir.async_delete_issue(self.hass, flow.handler, flow.context["issue_id"])
        return result


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Initialize repairs."""
    hass.data[DOMAIN]["flow_manager"] = RepairsFlowManager(hass)


async def async_process_repairs_platforms(hass: HomeAssistant) -> None:
    """Start processing repairs platforms."""
    hass.data[DOMAIN]["platforms"] = {}

    await async_process_integration_platforms(
        hass, DOMAIN, _register_repairs_platform, wait_for_platforms=True
    )


@callback
def _register_repairs_platform(
    hass: HomeAssistant, integration_domain: str, platform: RepairsProtocol
) -> None:
    """Register a repairs platform."""
    if not hasattr(platform, "async_create_fix_flow"):
        raise HomeAssistantError(f"Invalid repairs platform {platform}")
    hass.data[DOMAIN]["platforms"][integration_domain] = platform
