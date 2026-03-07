"""Models for Repairs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from homeassistant import data_entry_flow
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlowResult,
    FlowType,
    SubentryFlowResult,
)
from homeassistant.core import HomeAssistant, callback


class RepairsFlowResult(
    data_entry_flow.FlowResult[data_entry_flow.FlowContext, tuple[str, str]]
):
    """Typed context dict for repairs flow."""

    next_flow: tuple[FlowType, str]
    # Frontend needs this to render the dialog.
    result: ConfigEntry


class RepairsFlow(
    data_entry_flow.FlowHandler[
        data_entry_flow.FlowContext, RepairsFlowResult, tuple[str, str]
    ]
):
    """Handle a flow for fixing an issue."""

    issue_id: str
    data: dict[str, str | int | float | None] | None

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
        flow: ConfigFlowResult | SubentryFlowResult
        entry_id: str
        try:
            if flow_type in {FlowType.CONFIG_FLOW, FlowType.CONFIG_SUBENTRIES_FLOW}:
                if flow_type == FlowType.CONFIG_FLOW:
                    flow = self.hass.config_entries.flow.async_get(flow_id)
                    entry_id = flow["context"]["entry_id"]
                else:  # subentry flow
                    flow = self.hass.config_entries.subentries.async_get(flow_id)
                    entry_id, _ = flow["handler"]
                if (
                    "context" not in flow
                    or flow["context"]["source"] != SOURCE_RECONFIGURE
                ):  # check if reconfigure flow
                    raise data_entry_flow.FlowError(
                        "Next flow must be a reconfigure flow"
                    )
            else:
                flow = self.hass.config_entries.options.async_get(flow_id)
                entry_id = flow["handler"]
        except data_entry_flow.UnknownFlow as ex:
            raise data_entry_flow.UnknownFlow(
                f"Unknown next flow: {flow_type}: {flow_id}"
            ) from ex
        result["result"] = self.hass.config_entries.async_get_known_entry(entry_id)
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
