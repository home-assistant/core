"""Light support for switch entities."""
from __future__ import annotations

from typing import Any, Callable, Sequence, cast

import voluptuous as vol

from homeassistant.components import switch
from homeassistant.components.light import PLATFORM_SCHEMA, LightEntity
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ENTITY_ID,
    CONF_NAME,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant, State, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

# mypy: allow-untyped-calls, allow-untyped-defs, no-check-untyped-defs

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
    async_add_entities: Callable[[Sequence[Entity]], None],
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Initialize Light Switch platform."""

    registry = await hass.helpers.entity_registry.async_get_registry()
    wrapped_switch = registry.async_get(config[CONF_ENTITY_ID])
    unique_id = wrapped_switch.unique_id if wrapped_switch else None

    async_add_entities(
        [
            LightSwitch(
                cast(str, config.get(CONF_NAME)),
                config[CONF_ENTITY_ID],
                unique_id,
            )
        ]
    )


class LightSwitch(LightEntity):
    """Represents a Switch as a Light."""

    def __init__(self, name: str, switch_entity_id: str, unique_id: str) -> None:
        """Initialize Light Switch."""
        self._name = name
        self._switch_entity_id = switch_entity_id
        self._unique_id = unique_id
        self._switch_state: State | None = None

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def is_on(self) -> bool:
        """Return true if light switch is on."""
        assert self._switch_state is not None
        return self._switch_state.state == STATE_ON

    @property
    def available(self) -> bool:
        """Return true if light switch is on."""
        return (
            self._switch_state is not None
            and self._switch_state.state != STATE_UNAVAILABLE
        )

    @property
    def should_poll(self) -> bool:
        """No polling needed for a light switch."""
        return False

    @property
    def unique_id(self):
        """Return the unique id of the light switch."""
        return self._unique_id

    async def async_turn_on(self, **kwargs):
        """Forward the turn_on command to the switch in this light switch."""
        data = {ATTR_ENTITY_ID: self._switch_entity_id}
        await self.hass.services.async_call(
            switch.DOMAIN,
            switch.SERVICE_TURN_ON,
            data,
            blocking=True,
            context=self._context,
        )

    async def async_turn_off(self, **kwargs):
        """Forward the turn_off command to the switch in this light switch."""
        data = {ATTR_ENTITY_ID: self._switch_entity_id}
        await self.hass.services.async_call(
            switch.DOMAIN,
            switch.SERVICE_TURN_OFF,
            data,
            blocking=True,
            context=self._context,
        )

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._switch_state = self.hass.states.get(self._switch_entity_id)

        @callback
        def async_state_changed_listener(*_: Any) -> None:
            """Handle child updates."""
            self._switch_state = self.hass.states.get(self._switch_entity_id)
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._switch_entity_id], async_state_changed_listener
            )
        )
