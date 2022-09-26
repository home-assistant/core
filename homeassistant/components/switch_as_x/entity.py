"""Base entity for the Switch as X integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import Event, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import Entity, EntityCategory, ToggleEntity
from homeassistant.helpers.event import async_track_state_change_event


class BaseEntity(Entity):
    """Represents a Switch as a X."""

    _attr_should_poll = False

    def __init__(
        self,
        name: str,
        switch_entity_id: str,
        unique_id: str | None,
        device_id: str | None = None,
        entity_category: EntityCategory | None = None,
    ) -> None:
        """Initialize Light Switch."""
        self._device_id = device_id
        self._attr_entity_category = entity_category
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._switch_entity_id = switch_entity_id

    @callback
    def async_state_changed_listener(self, event: Event | None = None) -> None:
        """Handle child updates."""
        if (
            state := self.hass.states.get(self._switch_entity_id)
        ) is None or state.state == STATE_UNAVAILABLE:
            self._attr_available = False
            return

        self._attr_available = True

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        @callback
        def _async_state_changed_listener(event: Event | None = None) -> None:
            """Handle child updates."""
            self.async_state_changed_listener(event)
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._switch_entity_id], _async_state_changed_listener
            )
        )

        # Call once on adding
        _async_state_changed_listener()

        # Add this entity to the wrapped switch's device
        registry = er.async_get(self.hass)
        if registry.async_get(self.entity_id) is not None:
            registry.async_update_entity(self.entity_id, device_id=self._device_id)


class BaseToggleEntity(BaseEntity, ToggleEntity):
    """Represents a Switch as a ToggleEntity."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward the turn_on command to the switch in this light switch."""
        await self.hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: self._switch_entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward the turn_off command to the switch in this light switch."""
        await self.hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: self._switch_entity_id},
            blocking=True,
            context=self._context,
        )

    @callback
    def async_state_changed_listener(self, event: Event | None = None) -> None:
        """Handle child updates."""
        super().async_state_changed_listener(event)
        if (
            not self.available
            or (state := self.hass.states.get(self._switch_entity_id)) is None
        ):
            return

        self._attr_is_on = state.state == STATE_ON
