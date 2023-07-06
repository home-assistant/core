"""Lock support for switch entities."""
from __future__ import annotations

from typing import Any

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN, LockEntity
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import BaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Lock Switch config entry."""
    registry = er.async_get(hass)
    entity_id = er.async_validate_entity_id(
        registry, config_entry.options[CONF_ENTITY_ID]
    )

    async_add_entities(
        [
            LockSwitch(
                hass,
                config_entry.title,
                LOCK_DOMAIN,
                entity_id,
                config_entry.entry_id,
            )
        ]
    )


class LockSwitch(BaseEntity, LockEntity):
    """Represents a Switch as a Lock."""

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        await self.hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: self._switch_entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        await self.hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
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

        # Logic is the same as the lock device class for binary sensors
        # on means open (unlocked), off means closed (locked)
        self._attr_is_locked = state.state != STATE_ON
