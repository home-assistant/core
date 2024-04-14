"""Location helpers for Home Assistant."""

from __future__ import annotations

from collections.abc import Iterable
import logging

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


def closest(latitude: float, longitude: float, states: Iterable[State]) -> State | None:
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
    hass: HomeAssistant, name: str, recursion_history: list | None = None
) -> str | None:
    """Try to resolve the a location from a supplied name or entity_id.

    Will recursively resolve an entity if pointed to by the state of the supplied
    entity.

    Returns coordinates in the form of '90.000,180.000', an address or
    the state of the last resolved entity.
    """
    # Check if a friendly name of a zone was supplied
    if (zone_coords := resolve_zone(hass, name)) is not None:
        return zone_coords

    # Check if an entity_id was supplied.
    if (entity_state := hass.states.get(name)) is None:
        _LOGGER.debug("Unable to find entity %s", name)
        return name

    # Check if the entity_state has location attributes
    if has_location(entity_state):
        return _get_location_from_attributes(entity_state)

    # Check if entity_state is a zone
    zone_entity = hass.states.get(f"zone.{entity_state.state}")
    if has_location(zone_entity):  # type: ignore[arg-type]
        _LOGGER.debug(
            "%s is in %s, getting zone location",
            name,
            zone_entity.entity_id,  # type: ignore[union-attr]
        )
        return _get_location_from_attributes(zone_entity)  # type: ignore[arg-type]

    # Check if entity_state is a friendly name of a zone
    if (zone_coords := resolve_zone(hass, entity_state.state)) is not None:
        return zone_coords

    # Check if entity_state is an entity_id
    if recursion_history is None:
        recursion_history = []
    recursion_history.append(name)
    if entity_state.state in recursion_history:
        _LOGGER.error(
            (
                "Circular reference detected while trying to find coordinates of an"
                " entity. The state of %s has already been checked"
            ),
            entity_state.state,
        )
        return None
    _LOGGER.debug("Getting nested entity for state: %s", entity_state.state)
    nested_entity = hass.states.get(entity_state.state)
    if nested_entity is not None:
        _LOGGER.debug("Resolving nested entity_id: %s", entity_state.state)
        return find_coordinates(hass, entity_state.state, recursion_history)

    # Might be an address, coordinates or anything else.
    # This has to be checked by the caller.
    return entity_state.state


def resolve_zone(hass: HomeAssistant, zone_name: str) -> str | None:
    """Get a lat/long from a zones friendly_name.

    None is returned if no zone is found by that friendly_name.
    """
    states = hass.states.async_all("zone")
    for state in states:
        if state.name == zone_name:
            return _get_location_from_attributes(state)

    return None


def _get_location_from_attributes(entity_state: State) -> str:
    """Get the lat/long string from an entities attributes."""
    attr = entity_state.attributes
    return f"{attr.get(ATTR_LATITUDE)},{attr.get(ATTR_LONGITUDE)}"
