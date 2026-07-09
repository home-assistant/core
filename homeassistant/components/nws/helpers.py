"""Helpers for the NWS integration."""

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    TrackerEntityStateAttribute,
)
from homeassistant.components.person import (
    DOMAIN as PERSON_DOMAIN,
    PersonEntityStateAttribute,
)
from homeassistant.components.zone import (
    DOMAIN as ZONE_DOMAIN,
    ZoneEntityStateAttribute,
)
from homeassistant.core import State


def location_coordinates(state: State) -> tuple[float, float]:
    """Return the coordinates of an NWS location entity state.

    Read via the enum matching the entity domain; the config flow only allows
    person, device_tracker and zone entities as the location source. Callers
    must ensure the state has valid coordinates (``has_location``).
    """
    if state.domain == PERSON_DOMAIN:
        return (
            state.attributes[PersonEntityStateAttribute.LATITUDE],
            state.attributes[PersonEntityStateAttribute.LONGITUDE],
        )
    if state.domain == DEVICE_TRACKER_DOMAIN:
        return (
            state.attributes[TrackerEntityStateAttribute.LATITUDE],
            state.attributes[TrackerEntityStateAttribute.LONGITUDE],
        )
    if state.domain == ZONE_DOMAIN:
        return (
            state.attributes[ZoneEntityStateAttribute.LATITUDE],
            state.attributes[ZoneEntityStateAttribute.LONGITUDE],
        )
    # Unreachable: the config flow restricts the location source to the three
    # domains above.
    raise RuntimeError(f"Unsupported location entity domain: {state.domain}")
