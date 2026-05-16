"""Sandbox proxy for event entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.core import callback

from . import SandboxEntityDescription, SandboxEntityManager, SandboxProxyEntity


class SandboxEventEntity(SandboxProxyEntity, EventEntity):
    """Proxy for an event entity in a sandbox."""

    _unrecorded_attributes = frozenset({})

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy event entity."""
        super().__init__(description, manager)
        self._attr_event_types = description.capabilities.get("event_types", [])

    @callback
    def sandbox_update_state(self, state: str, attributes: dict[str, Any]) -> None:
        """Handle event firing from sandbox."""
        event_type = attributes.get("event_type")
        if event_type:
            event_attributes = {
                k: v
                for k, v in attributes.items()
                if k not in ("event_type", "state")
            }
            self._trigger_event(event_type, event_attributes or None)
            self.async_write_ha_state()
        else:
            super().sandbox_update_state(state, attributes)
