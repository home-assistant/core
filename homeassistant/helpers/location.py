"""Location helpers for Home Assistant."""

from typing import Optional, Sequence

from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import State
from homeassistant.util import location as loc_util


def has_location(state: State) -> bool:
    """Test if state contains a valid location.

    Async friendly.
    """
    return (isinstance(state, State) and
            isinstance(state.attributes.get(ATTR_LATITUDE), float) and
            isinstance(state.attributes.get(ATTR_LONGITUDE), float))


def closest(latitude: float, longitude: float,
            states: Sequence[State]) -> Optional[State]:
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
            latitude, longitude)
    )
