"""The discovery flow helper."""
from __future__ import annotations

from collections.abc import Coroutine
from typing import Any

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, Event, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.loader import bind_hass
from homeassistant.util.async_ import gather_with_concurrency

FLOW_INIT_LIMIT = 2
DISCOVERY_FLOW_DISPATCHER = "discovery_flow_disptacher"


@bind_hass
@callback
def async_create_flow(
    hass: HomeAssistant, domain: str, context: dict[str, Any], data: Any
) -> None:
    """Create a discovery flow."""
    if DISCOVERY_FLOW_DISPATCHER not in hass.data:
        dispatcher = hass.data[DISCOVERY_FLOW_DISPATCHER] = FlowDispatcher(hass)
        dispatcher.async_setup()
    else:
        dispatcher = hass.data[DISCOVERY_FLOW_DISPATCHER]
    return dispatcher.async_create(domain, context, data)


class FlowDispatcher:
    """Dispatch discovery flows."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Init the discovery dispatcher."""
        self.hass = hass
        self.pending_flows: list[tuple[str, dict[str, Any], Any]] = []
        self.started = False

    @callback
    def async_setup(self) -> None:
        """Set up the flow disptcher."""
        if self.hass.state == CoreState.running:
            self.started = True
            return
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, self.async_start)

    @callback
    def async_start(self, event: Event) -> None:
        """Start processing pending flows."""
        self.started = True
        self.hass.async_create_task(self._async_process_pending_flows())

    async def _async_process_pending_flows(self) -> None:
        """Process any pending discovery flows."""
        init_coros = [self._init_flow(*flow) for flow in self.pending_flows]
        await gather_with_concurrency(
            FLOW_INIT_LIMIT,
            *[init_coro for init_coro in init_coros if init_coro is not None],
        )

    @callback
    def async_create(self, domain: str, context: dict[str, Any], data: Any) -> None:
        """Create and add or queue a flow."""
        if self.started:
            if init_coro := self._init_flow(domain, context, data):
                self.hass.async_create_task(init_coro)
        else:
            self.pending_flows.append((domain, context, data))

    def _init_flow(
        self, domain: str, context: dict[str, Any], data: Any
    ) -> Coroutine[None, None, FlowResult] | None:
        """Create a flow."""
        # Avoid spawning flows that have the same initial discovery data
        # as ones in progress as it may cause additional device probing
        # which can overload devices since zeroconf/ssdp updates can happen
        # multiple times in the same minute
        if self.hass.config_entries.flow.async_has_matching_flow(domain, context, data):
            return None
        return self.hass.config_entries.flow.async_init(
            domain, context=context, data=data
        )
