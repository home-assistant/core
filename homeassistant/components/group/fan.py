"""This platform allows several fans to be grouped into one fan."""
from __future__ import annotations

from functools import reduce
import logging
from operator import ior
from typing import Any

import voluptuous as vol

from homeassistant.components.fan import (
    ATTR_DIRECTION,
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    ATTR_PERCENTAGE_STEP,
    DOMAIN,
    PLATFORM_SCHEMA,
    SERVICE_OSCILLATE,
    SERVICE_SET_DIRECTION,
    SERVICE_SET_PERCENTAGE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    FanEntity,
    FanEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_ENTITIES,
    CONF_NAME,
    CONF_UNIQUE_ID,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import GroupEntity
from .util import (
    attribute_equal,
    most_frequent_attribute,
    reduce_attribute,
    states_equal,
)

SUPPORTED_FLAGS = {
    FanEntityFeature.SET_SPEED,
    FanEntityFeature.DIRECTION,
    FanEntityFeature.OSCILLATE,
}

DEFAULT_NAME = "Fan Group"

# No limit on parallel updates to enable a group calling another group
PARALLEL_UPDATES = 0

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITIES): cv.entities_domain(DOMAIN),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Fan Group platform."""
    async_add_entities(
        [FanGroup(config.get(CONF_UNIQUE_ID), config[CONF_NAME], config[CONF_ENTITIES])]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Fan Group config entry."""
    registry = er.async_get(hass)
    entities = er.async_validate_entity_ids(
        registry, config_entry.options[CONF_ENTITIES]
    )

    async_add_entities([FanGroup(config_entry.entry_id, config_entry.title, entities)])


class FanGroup(GroupEntity, FanEntity):
    """Representation of a FanGroup."""

    _attr_available: bool = False
    _attr_assumed_state: bool = True

    def __init__(self, unique_id: str | None, name: str, entities: list[str]) -> None:
        """Initialize a FanGroup entity."""
        self._entities = entities
        self._fans: dict[int, set[str]] = {flag: set() for flag in SUPPORTED_FLAGS}
        self._percentage = None
        self._oscillating = None
        self._direction = None
        self._supported_features = 0
        self._speed_count = 100
        self._is_on: bool | None = False
        self._attr_name = name
        self._attr_extra_state_attributes = {ATTR_ENTITY_ID: entities}
        self._attr_unique_id = unique_id

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._supported_features

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return self._speed_count

    @property
    def is_on(self) -> bool | None:
        """Return true if the entity is on."""
        return self._is_on

    @property
    def percentage(self) -> int | None:
        """Return the current speed as a percentage."""
        return self._percentage

    @property
    def current_direction(self) -> str | None:
        """Return the current direction of the fan."""
        return self._direction

    @property
    def oscillating(self) -> bool | None:
        """Return whether or not the fan is currently oscillating."""
        return self._oscillating

    @callback
    def _update_supported_features_event(self, event: Event) -> None:
        self.async_set_context(event.context)
        if (entity := event.data.get("entity_id")) is not None:
            self.async_update_supported_features(entity, event.data.get("new_state"))

    @callback
    def async_update_supported_features(
        self,
        entity_id: str,
        new_state: State | None,
        update_state: bool = True,
    ) -> None:
        """Update dictionaries with supported features."""
        if not new_state:
            for values in self._fans.values():
                values.discard(entity_id)
        else:
            features = new_state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
            for feature in SUPPORTED_FLAGS:
                if features & feature:
                    self._fans[feature].add(entity_id)
                else:
                    self._fans[feature].discard(entity_id)

        if update_state:
            self.async_defer_or_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register listeners."""
        for entity_id in self._entities:
            if (new_state := self.hass.states.get(entity_id)) is None:
                continue
            self.async_update_supported_features(
                entity_id, new_state, update_state=False
            )
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._entities, self._update_supported_features_event
            )
        )

        await super().async_added_to_hass()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        if percentage == 0:
            await self.async_turn_off()
        await self._async_call_supported_entities(
            SERVICE_SET_PERCENTAGE,
            FanEntityFeature.SET_SPEED,
            {ATTR_PERCENTAGE: percentage},
        )

    async def async_oscillate(self, oscillating: bool) -> None:
        """Oscillate the fan."""
        await self._async_call_supported_entities(
            SERVICE_OSCILLATE,
            FanEntityFeature.OSCILLATE,
            {ATTR_OSCILLATING: oscillating},
        )

    async def async_set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        await self._async_call_supported_entities(
            SERVICE_SET_DIRECTION,
            FanEntityFeature.DIRECTION,
            {ATTR_DIRECTION: direction},
        )

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        if percentage is not None:
            await self.async_set_percentage(percentage)
            return
        await self._async_call_all_entities(SERVICE_TURN_ON)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fans off."""
        await self._async_call_all_entities(SERVICE_TURN_OFF)

    async def _async_call_supported_entities(
        self, service: str, support_flag: int, data: dict[str, Any]
    ) -> None:
        """Call a service with all entities."""
        await self.hass.services.async_call(
            DOMAIN,
            service,
            {**data, ATTR_ENTITY_ID: self._fans[support_flag]},
            blocking=True,
            context=self._context,
        )

    async def _async_call_all_entities(self, service: str) -> None:
        """Call a service with all entities."""
        await self.hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_ENTITY_ID: self._entities},
            blocking=True,
            context=self._context,
        )

    def _async_states_by_support_flag(self, flag: int) -> list[State]:
        """Return all the entity states for a supported flag."""
        states: list[State] = list(
            filter(None, [self.hass.states.get(x) for x in self._fans[flag]])
        )
        return states

    def _set_attr_most_frequent(self, attr: str, flag: int, entity_attr: str) -> None:
        """Set an attribute based on most frequent supported entities attributes."""
        states = self._async_states_by_support_flag(flag)
        setattr(self, attr, most_frequent_attribute(states, entity_attr))
        self._attr_assumed_state |= not attribute_equal(states, entity_attr)

    @callback
    def async_update_group_state(self) -> None:
        """Update state and attributes."""
        self._attr_assumed_state = False

        states = [
            state
            for entity_id in self._entities
            if (state := self.hass.states.get(entity_id)) is not None
        ]
        self._attr_assumed_state |= not states_equal(states)

        # Set group as unavailable if all members are unavailable or missing
        self._attr_available = any(state.state != STATE_UNAVAILABLE for state in states)

        valid_state = any(
            state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE) for state in states
        )
        if not valid_state:
            # Set as unknown if all members are unknown or unavailable
            self._is_on = None
        else:
            # Set as ON if any member is ON
            self._is_on = any(state.state == STATE_ON for state in states)

        percentage_states = self._async_states_by_support_flag(
            FanEntityFeature.SET_SPEED
        )
        self._percentage = reduce_attribute(percentage_states, ATTR_PERCENTAGE)
        self._attr_assumed_state |= not attribute_equal(
            percentage_states, ATTR_PERCENTAGE
        )
        if (
            percentage_states
            and percentage_states[0].attributes.get(ATTR_PERCENTAGE_STEP)
            and attribute_equal(percentage_states, ATTR_PERCENTAGE_STEP)
        ):
            self._speed_count = (
                round(100 / percentage_states[0].attributes[ATTR_PERCENTAGE_STEP])
                or 100
            )
        else:
            self._speed_count = 100

        self._set_attr_most_frequent(
            "_oscillating", FanEntityFeature.OSCILLATE, ATTR_OSCILLATING
        )
        self._set_attr_most_frequent(
            "_direction", FanEntityFeature.DIRECTION, ATTR_DIRECTION
        )

        self._supported_features = reduce(
            ior, [feature for feature in SUPPORTED_FLAGS if self._fans[feature]], 0
        )
        self._attr_assumed_state |= any(
            state.attributes.get(ATTR_ASSUMED_STATE) for state in states
        )
