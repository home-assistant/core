"""Sandbox-side event mirror.

Forwards every event whose ``event_type`` matches ``<approved_domain>_*``
up to main via ``sandbox/fire_event``. Canonical examples: ``zha_event``,
``mqtt_message_received``, ``hue_event``, ``device_tracker_see``.

The bus listener is installed via ``MATCH_ALL`` so we don't need to know
the integration's event names ahead of time, with a callback-decorated
event filter so the bus can short-circuit on a fast path before queuing
the listener. Untrusted (non-approved) event types are silently dropped
— they would never have been forwarded anyway and don't deserve a log
line per event.

System events that already cross the bridge through dedicated channels
(``EVENT_STATE_CHANGED``, ``EVENT_SERVICE_REGISTERED``, …) are
suppressed unconditionally; ``state_changed`` for example is owned by
:class:`hass_client.entity_bridge.EntityBridge` and re-emitting it as a
plain event would double-count.
"""

import asyncio
import logging
from typing import Any

from homeassistant.const import (
    EVENT_CALL_SERVICE,
    EVENT_COMPONENT_LOADED,
    EVENT_CORE_CONFIG_UPDATE,
    EVENT_HOMEASSISTANT_CLOSE,
    EVENT_HOMEASSISTANT_FINAL_WRITE,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_LOGGING_CHANGED,
    EVENT_SERVICE_REGISTERED,
    EVENT_SERVICE_REMOVED,
    EVENT_STATE_CHANGED,
    EVENT_STATE_REPORTED,
    MATCH_ALL,
)
from homeassistant.core import Event, HomeAssistant, callback

from ._proto import sandbox_pb2 as pb
from .approved_domains import ApprovedDomains
from .channel import Channel
from .protocol import MSG_FIRE_EVENT

_LOGGER = logging.getLogger(__name__)

# Events that are part of the bridge's own protocol or core lifecycle.
# Forwarding them either double-counts (state_changed is the entity
# bridge's job) or is meaningless on main (the sandbox's lifecycle is
# not main's).
_INTERNAL_EVENTS: frozenset[str] = frozenset(
    {
        EVENT_STATE_CHANGED,
        EVENT_STATE_REPORTED,
        EVENT_SERVICE_REGISTERED,
        EVENT_SERVICE_REMOVED,
        EVENT_CALL_SERVICE,
        EVENT_COMPONENT_LOADED,
        EVENT_CORE_CONFIG_UPDATE,
        EVENT_HOMEASSISTANT_START,
        EVENT_HOMEASSISTANT_STARTED,
        EVENT_HOMEASSISTANT_STOP,
        EVENT_HOMEASSISTANT_CLOSE,
        EVENT_HOMEASSISTANT_FINAL_WRITE,
        EVENT_LOGGING_CHANGED,
    }
)


class EventMirror:
    """Forward ``<approved_domain>_*`` events from the sandbox bus to main."""

    def __init__(self, hass: HomeAssistant, approved: ApprovedDomains) -> None:
        """Initialise with the sandbox HA and the shared approved-domains gate."""
        self.hass = hass
        self.approved = approved
        self._channel: Channel | None = None
        self._unsub: Any = None

    def register(self, channel: Channel) -> None:
        """Capture ``channel`` and start watching every event on the bus."""
        self._channel = channel
        # MATCH_ALL avoids re-subscribing every time the approved-domain
        # set grows. The handler does the cheap prefix check itself.
        self._unsub = self.hass.bus.async_listen(MATCH_ALL, self._on_event)

    async def async_stop(self) -> None:
        """Detach the bus listener."""
        if self._unsub is not None:
            self._unsub()
            self._unsub = None

    @callback
    def _on_event(self, event: Event) -> None:
        if self._channel is None or self._channel.closed:
            return
        event_type = event.event_type
        if event_type in _INTERNAL_EVENTS:
            return
        if not self.approved.approves_event(event_type):
            return
        msg = pb.FireEvent(event_type=event_type)
        msg.event_data.update(_to_json_safe(dict(event.data)))
        # Forward only the context id — never parent_id / user_id.
        if event.context is not None and event.context.id:
            msg.context_id = event.context.id
        asyncio.create_task(  # noqa: RUF006
            self._push(msg),
            name=f"sandbox:fire_event:{event_type}",
        )

    async def _push(self, msg: pb.FireEvent) -> None:
        assert self._channel is not None
        try:
            await self._channel.push(MSG_FIRE_EVENT, msg)
        except Exception:
            _LOGGER.exception("EventMirror: forward failed for %s", msg.event_type)


def _to_json_safe(value: Any) -> Any:
    """JSON-coerce arbitrary event-data objects.

    Event data on the sandbox bus is best-effort: integrations can stash
    domain objects in there. We don't want a single non-serialisable
    field to drop the whole event, so we coerce recursively and fall
    back to ``str(value)`` for unknown shapes.
    """
    if isinstance(value, dict):
        return {str(k): _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_to_json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, (str, int, float, bool)):
        return enum_value
    return str(value)


__all__ = ["EventMirror"]
