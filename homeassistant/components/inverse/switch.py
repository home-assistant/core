"""Switch support for inverse entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import BaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize Switch Inverse config entry."""
    registry = er.async_get(hass)
    entity_id = er.async_validate_entity_id(registry, config_entry.data[CONF_ENTITY_ID])

    async_add_entities(
        [
            InverseSwitch(
                hass,
                config_entry.title,
                SWITCH_DOMAIN,
                entity_id,
                config_entry.entry_id,
            )
        ]
    )


class InverseSwitch(BaseEntity, SwitchEntity):
    """Represents an Inverse Switch."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on (inverted - calls turn_off)."""
        await self.hass.services.async_call(
            self._source_domain,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: self._source_entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off (inverted - calls turn_on)."""
        await self.hass.services.async_call(
            self._source_domain,
            SERVICE_TURN_ON,
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

        self._attr_is_on = state.state != STATE_ON
