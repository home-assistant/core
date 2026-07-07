"""Models for Repairs."""

from collections.abc import Mapping
from typing import Any, Protocol, override

from homeassistant import data_entry_flow
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlowResult,
    SubentryFlowResult,
)
from homeassistant.core import HomeAssistant, callback

from .const import FlowType


class RepairsFlowResult(
    data_entry_flow.FlowResult[data_entry_flow.FlowContext, str], total=False
):
    """Typed result dict."""

    next_flow: tuple[FlowType, str]
    result: ConfigEntry | None


class RepairsFlow(
    data_entry_flow.FlowHandler[data_entry_flow.FlowContext, RepairsFlowResult, str]
):
    """Handle a flow for fixing an issue."""

    issue_id: str
    data: dict[str, str | int | float | None] | None

    @override
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
        """Create an entry (fix a flow)."""
        result: RepairsFlowResult = super().async_create_entry(
            title=title,
            data=data,
            description=description,
            description_placeholders=description_placeholders,
        )

        self._async_set_next_flow_if_valid(result, next_flow)

        return result

    @override
    @callback
    def async_abort(
        self,
        *,
        reason: str,
        description_placeholders: Mapping[str, str] | None = None,
        next_flow: tuple[FlowType, str] | None = None,
    ) -> RepairsFlowResult:
        """Abort the flow (leave the issue unrepaired)."""
        result: RepairsFlowResult = super().async_abort(
            reason=reason, description_placeholders=description_placeholders
        )

        self._async_set_next_flow_if_valid(result, next_flow)

        return result

    @callback
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
            raise data_entry_flow.UnknownFlow("Invalid next_flow type")
        entry_id: str | None = None
        if flow_type == FlowType.CONFIG_FLOW:
            config_flow: ConfigFlowResult = self.hass.config_entries.flow.async_get(
                flow_id
            )
            entry_id = config_flow["context"].get("entry_id")
        elif flow_type == FlowType.CONFIG_SUBENTRIES_FLOW:
            subentry_flow: SubentryFlowResult = (
                self.hass.config_entries.subentries.async_get(flow_id)
            )
            entry_id, _ = subentry_flow["handler"]
        else:  # flow_type is guaranteed to be FlowType.OPTIONS_FLOW due to the previous check
            config_flow = self.hass.config_entries.options.async_get(flow_id)
            entry_id = config_flow["handler"]
        # entry_id can be None for config_flow["source"] not in [SOURCE_REAUTH, SOURCE_RECONFIGURE]
        # as these flows have not created a config entry yet and result["result"] is expected to be None
        result["result"] = (
            self.hass.config_entries.async_get_known_entry(entry_id)
            if entry_id is not None
            else None
        )
        result["next_flow"] = next_flow


class RepairsProtocol(Protocol):
    """Define the format of repairs platforms."""

    async def async_create_fix_flow(
        self,
        hass: HomeAssistant,
        issue_id: str,
        data: dict[str, str | int | float | None] | None,
    ) -> RepairsFlow:
        """Create a flow to fix a fixable issue."""
