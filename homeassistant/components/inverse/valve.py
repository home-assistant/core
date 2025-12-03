"""Valve support for inverse entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.valve import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    DOMAIN as VALVE_DOMAIN,
    ValveEntity,
    ValveEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ENTITY_ID,
    SERVICE_CLOSE_VALVE,
    SERVICE_OPEN_VALVE,
    SERVICE_SET_VALVE_POSITION,
    SERVICE_STOP_VALVE,
    SERVICE_TOGGLE,
    STATE_OPEN,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import BaseInverseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize Valve Inverse config entry."""
    registry = er.async_get(hass)
    entity_id = er.async_validate_entity_id(registry, config_entry.data[CONF_ENTITY_ID])

    async_add_entities(
        [
            InverseValve(
                hass,
                config_entry.title,
                VALVE_DOMAIN,
                entity_id,
                config_entry.entry_id,
            )
        ]
    )


class InverseValve(BaseInverseEntity, ValveEntity):
    """Represents an Inverse Valve."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry_title: str,
        domain: str,
        source_entity_id: str,
        unique_id: str,
    ) -> None:
        """Initialize Inverse Valve."""
        super().__init__(hass, config_entry_title, domain, source_entity_id, unique_id)

        # Copy supported features and reports_position from source entity
        if source_state := hass.states.get(source_entity_id):
            if (
                supported_features := source_state.attributes.get("supported_features")
            ) is not None:
                self._attr_supported_features = ValveEntityFeature(supported_features)
            else:
                self._attr_supported_features = (
                    ValveEntityFeature.OPEN
                    | ValveEntityFeature.CLOSE
                    | ValveEntityFeature.SET_POSITION
                )

            self._attr_reports_position = source_state.attributes.get(
                "reports_position", False
            )

    async def async_open_valve(self, **kwargs: Any) -> None:
        """Open the valve (inverted - calls close)."""
        await self.hass.services.async_call(
            self._source_domain,
            SERVICE_CLOSE_VALVE,
            {ATTR_ENTITY_ID: self._source_entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_close_valve(self, **kwargs: Any) -> None:
        """Close valve (inverted - calls open)."""
        await self.hass.services.async_call(
            self._source_domain,
            SERVICE_OPEN_VALVE,
            {ATTR_ENTITY_ID: self._source_entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_set_valve_position(self, position: int) -> None:
        """Move the valve to a specific position (inverted)."""
        if position is not None:
            # Invert position: 0 -> 100, 100 -> 0
            inverted_position = 100 - position
            await self.hass.services.async_call(
                self._source_domain,
                SERVICE_SET_VALVE_POSITION,
                {
                    ATTR_ENTITY_ID: self._source_entity_id,
                    ATTR_POSITION: inverted_position,
                },
                blocking=True,
                context=self._context,
            )

    async def async_stop_valve(self, **kwargs: Any) -> None:
        """Stop the valve (not inverted)."""
        await self.hass.services.async_call(
            self._source_domain,
            SERVICE_STOP_VALVE,
            {ATTR_ENTITY_ID: self._source_entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_toggle(self, **kwargs: Any) -> None:
        """Toggle the valve (not inverted - toggle is toggle)."""
        await self.hass.services.async_call(
            self._source_domain,
            SERVICE_TOGGLE,
            {ATTR_ENTITY_ID: self._source_entity_id},
            blocking=True,
            context=self._context,
        )

    @callback
    def async_state_changed_listener(
        self, event: Event[EventStateChangedData] | None = None
    ) -> None:
        """Handle child updates."""
        super().async_state_changed_listener(event)
        if (
            not self.available
            or (state := self.hass.states.get(self._source_entity_id)) is None
        ):
            return

        # Always invert: open becomes closed
        self._attr_is_closed = state.state == STATE_OPEN

        # Invert position: source 0 -> inverse 100, source 100 -> inverse 0
        if (
            current_position := state.attributes.get(ATTR_CURRENT_POSITION)
        ) is not None:
            self._attr_current_valve_position = 100 - current_position
