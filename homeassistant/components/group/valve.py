"""Platform allowing several valves to be grouped into one valve."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.valve import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    DOMAIN as VALVE_DOMAIN,
    PLATFORM_SCHEMA as VALVE_PLATFORM_SCHEMA,
    ValveEntity,
    ValveEntityFeature,
    ValveState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_ENTITIES,
    CONF_NAME,
    CONF_UNIQUE_ID,
    SERVICE_CLOSE_VALVE,
    SERVICE_OPEN_VALVE,
    SERVICE_SET_VALVE_POSITION,
    SERVICE_STOP_VALVE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .entity import GroupEntity
from .util import reduce_attribute

KEY_OPEN_CLOSE = "open_close"
KEY_STOP = "stop"
KEY_SET_POSITION = "set_position"

DEFAULT_NAME = "Valve Group"

# No limit on parallel updates to enable a group calling another group
PARALLEL_UPDATES = 0

PLATFORM_SCHEMA = VALVE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITIES): cv.entities_domain(VALVE_DOMAIN),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    disvalvey_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Valve Group platform."""
    async_add_entities(
        [
            ValveGroup(
                config.get(CONF_UNIQUE_ID), config[CONF_NAME], config[CONF_ENTITIES]
            )
        ]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize Valve Group config entry."""
    registry = er.async_get(hass)
    entities = er.async_validate_entity_ids(
        registry, config_entry.options[CONF_ENTITIES]
    )

    async_add_entities(
        [ValveGroup(config_entry.entry_id, config_entry.title, entities)]
    )


@callback
def async_create_preview_valve(
    hass: HomeAssistant, name: str, validated_config: dict[str, Any]
) -> ValveGroup:
    """Create a preview sensor."""
    return ValveGroup(
        None,
        name,
        validated_config[CONF_ENTITIES],
    )


class ValveGroup(GroupEntity, ValveEntity):
    """Representation of a ValveGroup."""

    _attr_available: bool = False
    _attr_current_valve_position: int | None = None
    _attr_is_closed: bool | None = None
    _attr_is_closing: bool | None = False
    _attr_is_opening: bool | None = False
    _attr_reports_position: bool = False

    def __init__(self, unique_id: str | None, name: str, entities: list[str]) -> None:
        """Initialize a ValveGroup entity."""
        self._entity_ids = entities
        self._valves: dict[str, set[str]] = {
            KEY_OPEN_CLOSE: set(),
            KEY_STOP: set(),
            KEY_SET_POSITION: set(),
        }

        self._attr_name = name
        self._attr_extra_state_attributes = {ATTR_ENTITY_ID: entities}
        self._attr_unique_id = unique_id

    @callback
    def async_update_supported_features(
        self,
        entity_id: str,
        new_state: State | None,
    ) -> None:
        """Update dictionaries with supported features."""
        if not new_state:
            for values in self._valves.values():
                values.discard(entity_id)
            return

        features = new_state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        if features & (ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE):
            self._valves[KEY_OPEN_CLOSE].add(entity_id)
        else:
            self._valves[KEY_OPEN_CLOSE].discard(entity_id)
        if features & (ValveEntityFeature.STOP):
            self._valves[KEY_STOP].add(entity_id)
        else:
            self._valves[KEY_STOP].discard(entity_id)
        if features & (ValveEntityFeature.SET_POSITION):
            self._valves[KEY_SET_POSITION].add(entity_id)
        else:
            self._valves[KEY_SET_POSITION].discard(entity_id)

    async def async_open_valve(self) -> None:
        """Open the valves."""
        data = {ATTR_ENTITY_ID: self._valves[KEY_OPEN_CLOSE]}
        await self.hass.services.async_call(
            VALVE_DOMAIN, SERVICE_OPEN_VALVE, data, blocking=True, context=self._context
        )

    async def async_handle_open_valve(self) -> None:  # type: ignore[misc]
        """Open the valves.

        Override the base class to avoid calling the set position service
        for all valves. Transfer the service call to the base class and let
        it decide if the valve uses set position or open service.
        """
        await self.async_open_valve()

    async def async_close_valve(self) -> None:
        """Close valves."""
        data = {ATTR_ENTITY_ID: self._valves[KEY_OPEN_CLOSE]}
        await self.hass.services.async_call(
            VALVE_DOMAIN,
            SERVICE_CLOSE_VALVE,
            data,
            blocking=True,
            context=self._context,
        )

    async def async_handle_close_valve(self) -> None:  # type: ignore[misc]
        """Close the valves.

        Override the base class to avoid calling the set position service
        for all valves. Transfer the service call to the base class and let
        it decide if the valve uses set position or close service.
        """
        await self.async_close_valve()

    async def async_set_valve_position(self, position: int) -> None:
        """Move the valves to a specific position."""
        data = {
            ATTR_ENTITY_ID: self._valves[KEY_SET_POSITION],
            ATTR_POSITION: position,
        }
        await self.hass.services.async_call(
            VALVE_DOMAIN,
            SERVICE_SET_VALVE_POSITION,
            data,
            blocking=True,
            context=self._context,
        )

    async def async_stop_valve(self) -> None:
        """Stop the valves."""
        data = {ATTR_ENTITY_ID: self._valves[KEY_STOP]}
        await self.hass.services.async_call(
            VALVE_DOMAIN, SERVICE_STOP_VALVE, data, blocking=True, context=self._context
        )

    @callback
    def async_update_group_state(self) -> None:
        """Update state and attributes."""
        states = [
            state
            for entity_id in self._entity_ids
            if (state := self.hass.states.get(entity_id)) is not None
        ]

        # Set group as unavailable if all members are unavailable or missing
        self._attr_available = any(state.state != STATE_UNAVAILABLE for state in states)

        self._attr_is_closed = True
        self._attr_is_closing = False
        self._attr_is_opening = False
        self._attr_reports_position = False
        self._update_assumed_state_from_members()
        for state in states:
            if state.attributes.get(ATTR_CURRENT_POSITION) is not None:
                self._attr_reports_position = True
            if state.state == ValveState.OPEN:
                self._attr_is_closed = False
                continue
            if state.state == ValveState.CLOSED:
                continue
            if state.state == ValveState.CLOSING:
                self._attr_is_closing = True
                continue
            if state.state == ValveState.OPENING:
                self._attr_is_opening = True
                continue

        valid_state = any(
            state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE) for state in states
        )
        if not valid_state:
            # Set as unknown if all members are unknown or unavailable
            self._attr_is_closed = None

        self._attr_current_valve_position = reduce_attribute(
            states, ATTR_CURRENT_POSITION
        )

        supported_features = ValveEntityFeature(0)
        if self._valves[KEY_OPEN_CLOSE]:
            supported_features |= ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
        if self._valves[KEY_STOP]:
            supported_features |= ValveEntityFeature.STOP
        if self._valves[KEY_SET_POSITION]:
            supported_features |= ValveEntityFeature.SET_POSITION
        self._attr_supported_features = supported_features
