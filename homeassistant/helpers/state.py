"""
homeassistant.helpers.state
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Helpers that help with state related things.
"""
import logging

from homeassistant.core import State
import homeassistant.util.dt as dt_util
from homeassistant.const import (
    STATE_ON, STATE_OFF, SERVICE_TURN_ON, SERVICE_TURN_OFF,
    SERVICE_MEDIA_PLAY, SERVICE_MEDIA_PAUSE,
    STATE_PLAYING, STATE_PAUSED, ATTR_ENTITY_ID)

from homeassistant.components.media_player import (SERVICE_PLAY_MEDIA)

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
            _LOGGER.warning('reproduce_state: Unable to find entity %s',
                            state.entity_id)
            continue

        if state.domain == 'media_player' and state.attributes and \
            'media_type' in state.attributes and \
                'media_id' in state.attributes:
            service = SERVICE_PLAY_MEDIA
        elif state.domain == 'media_player' and state.state == STATE_PAUSED:
            service = SERVICE_MEDIA_PAUSE
        elif state.domain == 'media_player' and state.state == STATE_PLAYING:
            service = SERVICE_MEDIA_PLAY
        elif state.state == STATE_ON:
            service = SERVICE_TURN_ON
        elif state.state == STATE_OFF:
            service = SERVICE_TURN_OFF
        else:
            _LOGGER.warning("reproduce_state: Unable to reproduce state %s",
                            state)
            continue

        service_data = dict(state.attributes)
        service_data[ATTR_ENTITY_ID] = state.entity_id

        hass.services.call(state.domain, service, service_data, blocking)
