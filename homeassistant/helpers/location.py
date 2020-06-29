"""Location helpers for Home Assistant."""

import logging
from typing import Optional, Sequence

import voluptuous as vol

from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import State
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import location as loc_util

_LOGGER = logging.getLogger(__name__)


def has_location(state: State) -> bool:
    """Test if state contains a valid location.

    Async friendly.
    """
    # type ignore: https://github.com/python/mypy/issues/7207
    return (
        isinstance(state, State)  # type: ignore
        and isinstance(state.attributes.get(ATTR_LATITUDE), float)
        and isinstance(state.attributes.get(ATTR_LONGITUDE), float)
    )


def closest(
    latitude: float, longitude: float, states: Sequence[State]
) -> Optional[State]:
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
        ),
    )


def coordinates(
    hass: HomeAssistantType, entity_id: str, recursion_history: Optional[list] = None
) -> Optional[str]:
    """Get the location from the entity state or attributes."""
    entity = hass.states.get(entity_id)

    if entity is None:
        _LOGGER.error("Unable to find entity %s", entity_id)
        return None

    # Check if the entity has location attributes
    if has_location(entity):
        return _get_location_from_attributes(entity)

    # Check if device is in a zone
    zone_entity = hass.states.get(f"zone.{entity.state}")
    if has_location(zone_entity):  # type: ignore
        _LOGGER.debug(
            "%s is in %s, getting zone location", entity_id, zone_entity.entity_id  # type: ignore
        )
        return _get_location_from_attributes(zone_entity)  # type: ignore

    # Resolve nested entity
    if recursion_history is None:
        recursion_history = []
    recursion_history.append(entity_id)
    if entity.state in recursion_history:
        _LOGGER.error(
            "Circular Reference detected. The state of %s has already been checked.",
            entity.state,
        )
        return None
    _LOGGER.debug("Getting nested entity for state: %s", entity.state)
    nested_entity = hass.states.get(entity.state)
    if nested_entity is not None:
        _LOGGER.debug("Resolving nested entity_id: %s", entity.state)
        return coordinates(hass, entity.state, recursion_history)

    # Check if state is valid coordinate set
    try:
        cv.gps(entity.state.split(","))
    except vol.Invalid:
        _LOGGER.error(
            "The state of %s is not a valid set of coordinates: %s",
            entity_id,
            entity.state,
        )
        return None
    else:
        return entity.state


def _get_location_from_attributes(entity: State) -> str:
    """Get the lat/long string from an entities attributes."""
    attr = entity.attributes
    return "{},{}".format(attr.get(ATTR_LATITUDE), attr.get(ATTR_LONGITUDE))
