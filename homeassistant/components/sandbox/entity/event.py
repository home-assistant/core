"""Sandbox v2 proxy for ``event`` entities."""

from typing import Any

from homeassistant.components.event import ATTR_EVENT_TYPE, EventEntity
from homeassistant.core import Context
from homeassistant.util import dt as dt_util

from . import SandboxProxyEntity


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxEventEntity(SandboxProxyEntity, EventEntity):
    """Proxy for an ``event`` entity in a sandbox.

    ``EventEntity`` marks ``state`` and ``state_attributes`` ``@final``,
    so we set the name-mangled fields directly in
    :meth:`sandbox_apply_state` and let the framework recompute the
    state through the existing getters.
    """

    @property
    def event_types(self) -> list[str]:
        """Surface the cached list of event types."""
        return list(self.description.capabilities.get("event_types") or [])

    def sandbox_apply_state(
        self,
        state: str | None,
        attributes: dict[str, Any],
        context: Context | None = None,
    ) -> None:
        """Replay the sandbox-side event into the EventEntity fields."""
        # pylint: disable=attribute-defined-outside-init
        if state is None or state in ("unavailable", "unknown"):
            self._EventEntity__last_event_triggered = None
            self._EventEntity__last_event_type = None
            self._EventEntity__last_event_attributes = None
        else:
            self._EventEntity__last_event_triggered = dt_util.parse_datetime(state)
            event_attrs = dict(attributes)
            self._EventEntity__last_event_type = event_attrs.pop(ATTR_EVENT_TYPE, None)
            self._EventEntity__last_event_attributes = event_attrs or None
        super().sandbox_apply_state(state, attributes, context)
