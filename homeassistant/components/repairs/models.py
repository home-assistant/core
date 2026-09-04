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


class RepairsFlowContext(data_entry_flow.FlowContext, total=False):
    """Typed flow context for repairs flow."""

    issue_id: str


class RepairsFlowResult(
    data_entry_flow.FlowResult[
        RepairsFlowContext,
        str,
    ],
    total=False,
):
    """Typed result dict for repairs flow."""

    next_flow: tuple[FlowType, str]
    result: ConfigEntry | None


class RepairsFlow(
    data_entry_flow.FlowHandler[
        RepairsFlowContext,
        RepairsFlowResult,
        str,
    ]
):
    """Handle a flow for fixing an issue."""

    data: dict[str, str | int | float | None] | None
    _issue_id: str

    @property
    def issue_id(self) -> str:
        """Return the flow's issue_id."""
        if "issue_id" in self.context:
            return self.context["issue_id"]
        # Avoid breaking changes in legacy custom integrations that may access
        # this property prior to the flow manager applying the context in async_create_flow.
        return self._issue_id

    @issue_id.setter
    def issue_id(self, issue_id: str) -> None:
        """Allow legacy implementations to set issue_id.

        Setter is retained to avoid breaking changes in custom integrations that may set issue_id in a RepairFlow
        prior to the flow manager applying the context.
        """
        self._issue_id = issue_id

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
        translation_domain: str | None = None,
        next_flow: tuple[FlowType, str] | None = None,
    ) -> RepairsFlowResult:
        """Abort the flow (leave the issue unrepaired)."""
        result: RepairsFlowResult = super().async_abort(
            reason=reason,
            description_placeholders=description_placeholders,
            translation_domain=translation_domain,
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
            raise data_entry_flow.UnknownFlow("Invalid next_flow FlowType")
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
        else:  # FlowType.OPTIONS_FLOW
            config_flow = self.hass.config_entries.options.async_get(flow_id)
            entry_id = config_flow["handler"]
        # entry_id can be None for config flows creating a new config entry
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
