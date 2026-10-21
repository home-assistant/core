"""Sandbox-side event mirror."""

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
from .messages import MSG_FIRE_EVENT, encode_json

_LOGGER = logging.getLogger(__name__)

# Do not mirror entity state twice or forward worker lifecycle events to main.
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
        msg.event_data = encode_json(dict(event.data))
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


__all__ = ["EventMirror"]
