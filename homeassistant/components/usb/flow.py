"""The USB Discovery integration."""
from __future__ import annotations

from collections.abc import Coroutine
from typing import Any, TypedDict

from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult


class USBFlow(TypedDict):
    """A queued usb discovery flow."""

    domain: str
    context: dict[str, Any]
    data: dict


class FlowDispatcher:
    """Dispatch discovery flows."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Init the discovery dispatcher."""
        self.hass = hass
        self.pending_flows: list[USBFlow] = []
        self.started = False

    @callback
    def async_start(self, *_: Any) -> None:
        """Start processing pending flows."""
        self.started = True
        for flow in self.pending_flows:
            self.hass.async_create_task(self._init_flow(flow))
        self.pending_flows = []

    @callback
    def async_create(self, flow: USBFlow) -> None:
        """Create and add or queue a flow."""
        if self.started:
            self.hass.async_create_task(self._init_flow(flow))
        else:
            self.pending_flows.append(flow)

    def _init_flow(self, flow: USBFlow) -> Coroutine[None, None, FlowResult]:
        """Create a flow."""
        return self.hass.config_entries.flow.async_init(
            flow["domain"], context=flow["context"], data=flow["data"]
        )
