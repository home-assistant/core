"""State functions for Home Assistant templates."""

from __future__ import annotations

import collections.abc
from collections.abc import Iterable
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_PERSONS,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfLength,
)
from homeassistant.core import State, valid_entity_id
from homeassistant.helpers import location as loc_helper
from homeassistant.helpers.template.states import (
    AllStates,
    StateAttrTranslated,
    StateTranslated,
    _collect_state,
    _get_state,
    _resolve_state,
)
from homeassistant.util import convert, location as location_util

from .base import BaseTemplateExtension, TemplateFunction

if TYPE_CHECKING:
    from homeassistant.helpers.template import TemplateEnvironment

_LOGGER = logging.getLogger(__name__)

_SENTINEL = object()


class StateExtension(BaseTemplateExtension):
    """Jinja2 extension for state functions."""

    def __init__(self, environment: TemplateEnvironment) -> None:
        """Initialize the state extension."""
        # Build the class-based instance functions only when hass is available.
        # These use pass_context=False because they are callable class instances
        # that should not be wrapped by _pass_context.
        class_functions: list[TemplateFunction] = []
        if (hass := environment.hass) is not None:
            class_functions = [
                TemplateFunction(
                    "state_attr_translated",
                    StateAttrTranslated(hass),
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                    limited_ok=False,
                    pass_context=False,
                ),
                TemplateFunction(
                    "state_translated",
                    StateTranslated(hass),
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                    limited_ok=False,
                    pass_context=False,
                ),
                TemplateFunction(
                    "states",
                    AllStates(hass),
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                    limited_ok=False,
                    pass_context=False,
                ),
            ]

        super().__init__(
            environment,
            functions=[
                TemplateFunction(
                    "closest",
                    self.closest,
                    as_global=True,
                    requires_hass=True,
                    limited_ok=False,
                ),
                TemplateFunction(
                    "closest",
                    self.closest_filter,
                    as_filter=True,
                    requires_hass=True,
                    limited_ok=False,
                ),
                TemplateFunction(
                    "distance",
                    self.distance,
                    as_global=True,
                    requires_hass=True,
                    limited_ok=False,
                ),
                TemplateFunction(
                    "expand",
                    self.expand,
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                    limited_ok=False,
                ),
                TemplateFunction(
                    "has_value",
                    self.has_value,
                    as_global=True,
                    as_filter=True,
                    as_test=True,
                    requires_hass=True,
                    limited_ok=False,
                ),
                TemplateFunction(
                    "is_state",
                    self.is_state,
                    as_global=True,
                    as_test=True,
                    requires_hass=True,
                    limited_ok=False,
                ),
                TemplateFunction(
                    "is_state_attr",
                    self.is_state_attr,
                    as_global=True,
                    as_test=True,
                    requires_hass=True,
                    limited_ok=False,
                ),
                TemplateFunction(
                    "state_attr",
                    self.state_attr,
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                    limited_ok=False,
                ),
                *class_functions,
            ],
        )

    def expand(self, *args: Any) -> Iterable[State]:
        """Expand out any groups and zones into entity states."""
        # circular import.
        from homeassistant.helpers import entity as entity_helper  # noqa: PLC0415

        hass = self.hass
        search = list(args)
        found = {}
        sources = entity_helper.entity_sources(hass)
        while search:
            entity = search.pop()
            if isinstance(entity, str):
                entity_id = entity
                if (entity := _get_state(hass, entity)) is None:
                    continue
            elif isinstance(entity, State):
                entity_id = entity.entity_id
            elif isinstance(entity, collections.abc.Iterable):
                search += entity
                continue
            else:
                # ignore other types
                continue

            if entity_id in found:
                continue

            domain = entity.domain
            if domain == "group" or (
                (source := sources.get(entity_id)) and source["domain"] == "group"
            ):
                # Collect state will be called in here since it's wrapped
                if group_entities := entity.attributes.get(ATTR_ENTITY_ID):
                    search += group_entities
            elif domain == "zone":
                if zone_entities := entity.attributes.get(ATTR_PERSONS):
                    search += zone_entities
            else:
                _collect_state(hass, entity_id)
                found[entity_id] = entity

        return list(found.values())

    def closest(self, *args: Any) -> State | None:
        """Find closest entity.

        Closest to home:
            closest(states)
            closest(states.device_tracker)
            closest('group.children')
            closest(states.group.children)

        Closest to a point:
            closest(23.456, 23.456, 'group.children')
            closest('zone.school', 'group.children')
            closest(states.zone.school, 'group.children')

        As a filter:
            states | closest
            states.device_tracker | closest
            ['group.children', states.device_tracker] | closest
            'group.children' | closest(23.456, 23.456)
            states.device_tracker | closest('zone.school')
            'group.children' | closest(states.zone.school)

        """
        hass = self.hass
        if len(args) == 1:
            latitude = hass.config.latitude
            longitude = hass.config.longitude
            entities = args[0]

        elif len(args) == 2:
            point_state = _resolve_state(hass, args[0])

            if point_state is None:
                _LOGGER.warning("Closest:Unable to find state %s", args[0])
                return None
            if not loc_helper.has_location(point_state):
                _LOGGER.warning(
                    "Closest:State does not contain valid location: %s", point_state
                )
                return None

            latitude = point_state.attributes[ATTR_LATITUDE]
            longitude = point_state.attributes[ATTR_LONGITUDE]

            entities = args[1]

        else:
            latitude_arg = convert(args[0], float)
            longitude_arg = convert(args[1], float)

            if latitude_arg is None or longitude_arg is None:
                _LOGGER.warning(
                    "Closest:Received invalid coordinates: %s, %s", args[0], args[1]
                )
                return None

            latitude = latitude_arg
            longitude = longitude_arg

            entities = args[2]

        states = self.expand(entities)

        # state will already be wrapped here
        return loc_helper.closest(latitude, longitude, states)

    def closest_filter(self, *args: Any) -> State | None:
        """Call closest as a filter. Need to reorder arguments."""
        new_args = list(args[1:])
        new_args.append(args[0])
        return self.closest(*new_args)

    def distance(self, *args: Any) -> float | None:
        """Calculate distance.

        Will calculate distance from home to a point or between points.
        Points can be passed in using state objects or lat/lng coordinates.
        """
        hass = self.hass
        locations: list[tuple[float, float]] = []

        to_process = list(args)

        while to_process:
            value = to_process.pop(0)
            if isinstance(value, str) and not valid_entity_id(value):
                point_state = None
            else:
                point_state = _resolve_state(hass, value)

            if point_state is None:
                # We expect this and next value to be lat&lng
                if not to_process:
                    _LOGGER.warning(
                        "Distance:Expected latitude and longitude, got %s", value
                    )
                    return None

                value_2 = to_process.pop(0)
                latitude_to_process = convert(value, float)
                longitude_to_process = convert(value_2, float)

                if latitude_to_process is None or longitude_to_process is None:
                    _LOGGER.warning(
                        "Distance:Unable to process latitude and longitude: %s, %s",
                        value,
                        value_2,
                    )
                    return None

                latitude = latitude_to_process
                longitude = longitude_to_process

            else:
                if not loc_helper.has_location(point_state):
                    _LOGGER.warning(
                        "Distance:State does not contain valid location: %s",
                        point_state,
                    )
                    return None

                latitude = point_state.attributes[ATTR_LATITUDE]
                longitude = point_state.attributes[ATTR_LONGITUDE]

            locations.append((latitude, longitude))

        if len(locations) == 1:
            return hass.config.distance(*locations[0])

        return hass.config.units.length(
            location_util.distance(*locations[0] + locations[1]), UnitOfLength.METERS
        )

    def is_state(self, entity_id: str, state: str | list[str]) -> bool:
        """Test if a state is a specific value."""
        state_obj = _get_state(self.hass, entity_id)
        return state_obj is not None and (
            state_obj.state == state
            or (isinstance(state, list) and state_obj.state in state)
        )

    def is_state_attr(self, entity_id: str, name: str, value: Any) -> bool:
        """Test if a state's attribute is a specific value."""
        if (state_obj := _get_state(self.hass, entity_id)) is not None:
            attr = state_obj.attributes.get(name, _SENTINEL)
            if attr is _SENTINEL:
                return False
            return bool(attr == value)
        return False

    def state_attr(self, entity_id: str, name: str) -> Any:
        """Get a specific attribute from a state."""
        if (state_obj := _get_state(self.hass, entity_id)) is not None:
            return state_obj.attributes.get(name)
        return None

    def has_value(self, entity_id: str) -> bool:
        """Test if an entity has a valid value."""
        state_obj = _get_state(self.hass, entity_id)

        return state_obj is not None and (
            state_obj.state not in [STATE_UNAVAILABLE, STATE_UNKNOWN]
        )
