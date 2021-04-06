"""Location helpers for Home Assistant."""
from __future__ import annotations

import logging
from typing import Sequence

import voluptuous as vol

from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import HomeAssistant, State
from homeassistant.util import location as loc_util

_LOGGER = logging.getLogger(__name__)


def has_location(state: State) -> bool:
    """Test if state contains a valid location.

    Async friendly.
    """
    return (
        isinstance(state, State)
        and isinstance(state.attributes.get(ATTR_LATITUDE), float)
        and isinstance(state.attributes.get(ATTR_LONGITUDE), float)
    )


def closest(latitude: float, longitude: float, states: Sequence[State]) -> State | None:
    """Return closest state to point.

    Async friendly.
    """
    with_location = [state for state in states if has_location(state)]

    if not with_location:
        return None

    return min(
        with_location,
        key=lambda state: loc_util.distance(
            state.attributes.get(ATTR_LATITUDE),
            state.attributes.get(ATTR_LONGITUDE),
            latitude,
            longitude,
        )
        or 0,
    )


def find_coordinates(
    hass: HomeAssistant, entity_id: str, recursion_history: list | None = None
) -> str | None:
    """Find the gps coordinates of the entity in the form of '90.000,180.000'."""
    entity_state = hass.states.get(entity_id)

    if entity_state is None:
        _LOGGER.error("Unable to find entity %s", entity_id)
        return None

    # Check if the entity has location attributes
    if has_location(entity_state):
        return _get_location_from_attributes(entity_state)

    # Check if device is in a zone
    zone_entity = hass.states.get(f"zone.{entity_state.state}")
    if has_location(zone_entity):  # type: ignore
        _LOGGER.debug(
            "%s is in %s, getting zone location", entity_id, zone_entity.entity_id  # type: ignore
        )
        return _get_location_from_attributes(zone_entity)  # type: ignore

    # Resolve nested entity
    if recursion_history is None:
        recursion_history = []
    recursion_history.append(entity_id)
    if entity_state.state in recursion_history:
        _LOGGER.error(
            "Circular reference detected while trying to find coordinates of an entity. The state of %s has already been checked",
            entity_state.state,
        )
        return None
    _LOGGER.debug("Getting nested entity for state: %s", entity_state.state)
    nested_entity = hass.states.get(entity_state.state)
    if nested_entity is not None:
        _LOGGER.debug("Resolving nested entity_id: %s", entity_state.state)
        return find_coordinates(hass, entity_state.state, recursion_history)

    # Check if state is valid coordinate set
    try:
        # Import here, not at top-level to avoid circular import
        import homeassistant.helpers.config_validation as cv  # pylint: disable=import-outside-toplevel

        cv.gps(entity_state.state.split(","))
    except vol.Invalid:
        _LOGGER.error(
            "Entity %s does not contain a location and does not point at an entity that does: %s",
            entity_id,
            entity_state.state,
        )
        return None
    else:
        return entity_state.state


def _get_location_from_attributes(entity_state: State) -> str:
    """Get the lat/long string from an entities attributes."""
    attr = entity_state.attributes
    return "{},{}".format(attr.get(ATTR_LATITUDE), attr.get(ATTR_LONGITUDE))
