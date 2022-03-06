"""Light support for switch entities."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import switch
from homeassistant.components.light import (
    COLOR_MODE_ONOFF,
    PLATFORM_SCHEMA,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ENTITY_ID,
    CONF_NAME,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

DEFAULT_NAME = "Light Switch"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_ENTITY_ID): cv.entity_domain(switch.DOMAIN),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Initialize Light Switch platform."""
    registry = er.async_get(hass)
    wrapped_switch = registry.async_get(config[CONF_ENTITY_ID])
    unique_id = wrapped_switch.unique_id if wrapped_switch else None

    async_add_entities(
        [
            LightSwitch(
                config[CONF_NAME],
                config[CONF_ENTITY_ID],
                unique_id,
            )
        ]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Light Switch config entry."""

    registry = er.async_get(hass)
    entity_id = er.async_validate_entity_id(
        registry, config_entry.options[CONF_ENTITY_ID]
    )

    async_add_entities(
        [
            LightSwitch(
                config_entry.title,
                entity_id,
                config_entry.entry_id,
            )
        ]
    )


class LightSwitch(LightEntity):
    """Represents a Switch as a Light."""

    _attr_color_mode = COLOR_MODE_ONOFF
    _attr_should_poll = False
    _attr_supported_color_modes = {COLOR_MODE_ONOFF}

    def __init__(self, name: str, switch_entity_id: str, unique_id: str | None) -> None:
        """Initialize Light Switch."""
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._switch_entity_id = switch_entity_id

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward the turn_on command to the switch in this light switch."""
        await self.hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: self._switch_entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward the turn_off command to the switch in this light switch."""
        await self.hass.services.async_call(
            switch.DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: self._switch_entity_id},
            blocking=True,
            context=self._context,
        )

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        @callback
        def async_state_changed_listener(event: Event | None = None) -> None:
            """Handle child updates."""
            if (
                state := self.hass.states.get(self._switch_entity_id)
            ) is None or state.state == STATE_UNAVAILABLE:
                self._attr_available = False
                return

            self._attr_available = True
            self._attr_is_on = state.state == STATE_ON
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._switch_entity_id], async_state_changed_listener
            )
        )

        # Call once on adding
        async_state_changed_listener()
