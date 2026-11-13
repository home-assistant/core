"""Helpers for the zone integration."""

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    DeviceTrackerEntityStateAttribute,
)
from homeassistant.components.person import (
    DOMAIN as PERSON_DOMAIN,
    PersonEntityStateAttribute,
)
from homeassistant.core import State


def get_in_zones_attribute(state: State) -> str | None:
    """Return the in_zones attribute for the tracked entity, or None.

    Only person and device_tracker entities report zone membership; each
    exposes it under its own platform enum. Any other domain returns None.
    """
    if state.domain == PERSON_DOMAIN:
        return PersonEntityStateAttribute.IN_ZONES
    if state.domain == DEVICE_TRACKER_DOMAIN:
        return DeviceTrackerEntityStateAttribute.IN_ZONES
    return None
