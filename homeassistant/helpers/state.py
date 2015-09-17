"""
homeassistant.helpers.state
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Helpers that help with state related things.
"""
import logging

from homeassistant.core import State
import homeassistant.util.dt as dt_util
from homeassistant.const import (
    STATE_ON, STATE_OFF, SERVICE_TURN_ON, SERVICE_TURN_OFF, ATTR_ENTITY_ID)

_LOGGER = logging.getLogger(__name__)


# pylint: disable=too-few-public-methods, attribute-defined-outside-init
class TrackStates(object):
    """
    Records the time when the with-block is entered. Will add all states
    that have changed since the start time to the return list when with-block
    is exited.
    """
    def __init__(self, hass):
        self.hass = hass
        self.states = []

    def __enter__(self):
        self.now = dt_util.utcnow()
        return self.states

    def __exit__(self, exc_type, exc_value, traceback):
        self.states.extend(get_changed_since(self.hass.states.all(), self.now))


def get_changed_since(states, utc_point_in_time):
    """
    Returns all states that have been changed since utc_point_in_time.
    """
    point_in_time = dt_util.strip_microseconds(utc_point_in_time)

    return [state for state in states if state.last_updated >= point_in_time]


def reproduce_state(hass, states, blocking=False):
    """ Takes in a state and will try to have the entity reproduce it. """
    if isinstance(states, State):
        states = [states]

    for state in states:
        current_state = hass.states.get(state.entity_id)

        if current_state is None:
            continue

        if state.state == STATE_ON:
            service = SERVICE_TURN_ON
        elif state.state == STATE_OFF:
            service = SERVICE_TURN_OFF
        else:
            _LOGGER.warning("Unable to reproduce state for %s", state)
            continue

        service_data = dict(state.attributes)
        service_data[ATTR_ENTITY_ID] = state.entity_id

        hass.services.call(state.domain, service, service_data, blocking)
