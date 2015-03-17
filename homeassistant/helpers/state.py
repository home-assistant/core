"""
homeassistant.helpers.state
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Helpers that help with state related things.
"""
import logging
from datetime import datetime

from homeassistant import State
from homeassistant.const import STATE_ON, STATE_OFF
import homeassistant.components as core_components

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
        self.now = datetime.now()
        return self.states

    def __exit__(self, exc_type, exc_value, traceback):
        self.states.extend(self.hass.states.get_since(self.now))


def reproduce_state(hass, states):
    """ Takes in a state and will try to have the entity reproduce it. """
    if isinstance(states, State):
        states = [states]

    for state in states:
        current_state = hass.states.get(state.entity_id)

        if current_state is None:
            continue

        if state.state == STATE_ON:
            core_components.turn_on(hass, state.entity_id, **state.attributes)
        elif state.state == STATE_OFF:
            core_components.turn_off(hass, state.entity_id, **state.attributes)
        else:
            _LOGGER.warning("Unable to reproduce state for %s", state)
