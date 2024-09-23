"""The discovery flow helper."""

from __future__ import annotations

from collections.abc import Coroutine
import dataclasses
from typing import TYPE_CHECKING, Any, NamedTuple, Self

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, Event, HomeAssistant, callback
from homeassistant.loader import bind_hass
from homeassistant.util.async_ import gather_with_limited_concurrency
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigFlowResult

FLOW_INIT_LIMIT = 20
DISCOVERY_FLOW_DISPATCHER: HassKey[FlowDispatcher] = HassKey(
    "discovery_flow_dispatcher"
)


@dataclasses.dataclass(kw_only=True, slots=True)
class DiscoveryKey:
    """Serializable discovery key."""

    domain: str
    key: str | tuple[str, ...]
    version: int

    @classmethod
    def from_json_dict(cls, json_dict: dict[str, Any]) -> Self:
        """Construct from JSON dict."""
        if type(key := json_dict["key"]) is list:
            key = tuple(key)
        return cls(domain=json_dict["domain"], key=key, version=json_dict["version"])


@bind_hass
@callback
def async_create_flow(
    hass: HomeAssistant,
    domain: str,
    context: dict[str, Any],
    data: Any,
    *,
    discovery_key: DiscoveryKey | None = None,
) -> None:
    """Create a discovery flow."""
    dispatcher: FlowDispatcher | None = None
    if DISCOVERY_FLOW_DISPATCHER in hass.data:
        dispatcher = hass.data[DISCOVERY_FLOW_DISPATCHER]
    elif hass.state is not CoreState.running:
        dispatcher = hass.data[DISCOVERY_FLOW_DISPATCHER] = FlowDispatcher(hass)
        dispatcher.async_setup()

    if discovery_key:
        context = context | {"discovery_key": discovery_key}

    if not dispatcher or dispatcher.started:
        if init_coro := _async_init_flow(hass, domain, context, data):
            hass.async_create_background_task(
                init_coro, f"discovery flow {domain} {context}", eager_start=True
            )
        return

    dispatcher.async_create(domain, context, data)


@callback
def _async_init_flow(
    hass: HomeAssistant, domain: str, context: dict[str, Any], data: Any
) -> Coroutine[None, None, ConfigFlowResult] | None:
    """Create a discovery flow."""
    # Avoid spawning flows that have the same initial discovery data
    # as ones in progress as it may cause additional device probing
    # which can overload devices since zeroconf/ssdp updates can happen
    # multiple times in the same minute
    if (
        hass.config_entries.flow.async_has_matching_flow(domain, context, data)
        or hass.is_stopping
    ):
        return None

    return hass.config_entries.flow.async_init(domain, context=context, data=data)


class PendingFlowKey(NamedTuple):
    """Key for pending flows."""

    domain: str
    source: str


class PendingFlowValue(NamedTuple):
    """Value for pending flows."""

    context: dict[str, Any]
    data: Any


class FlowDispatcher:
    """Dispatch discovery flows."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Init the discovery dispatcher."""
        self.hass = hass
        self.started = False
        self.pending_flows: dict[PendingFlowKey, list[PendingFlowValue]] = {}

    @callback
    def async_setup(self) -> None:
        """Set up the flow disptcher."""
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, self._async_start)

    async def _async_start(self, event: Event) -> None:
        """Start processing pending flows."""
        pending_flows = self.pending_flows
        self.pending_flows = {}
        self.started = True
        init_coros = (
            init_coro
            for flow_key, flows in pending_flows.items()
            for flow_values in flows
            if (
                init_coro := _async_init_flow(
                    self.hass,
                    flow_key.domain,
                    flow_values.context,
                    flow_values.data,
                )
            )
        )
        await gather_with_limited_concurrency(FLOW_INIT_LIMIT, *init_coros)

    @callback
    def async_create(self, domain: str, context: dict[str, Any], data: Any) -> None:
        """Create and add or queue a flow."""
        key = PendingFlowKey(domain, context["source"])
        values = PendingFlowValue(context, data)
        existing = self.pending_flows.setdefault(key, [])
        if not any(existing_values.data == data for existing_values in existing):
            existing.append(values)
