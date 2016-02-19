"""Helpers that help with state related things."""
import json
import logging
from collections import defaultdict

import homeassistant.util.dt as dt_util
from homeassistant.components.media_player import SERVICE_PLAY_MEDIA
from homeassistant.components.sun import (
    STATE_ABOVE_HORIZON, STATE_BELOW_HORIZON)
from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_MEDIA_PAUSE, SERVICE_MEDIA_PLAY, SERVICE_TURN_OFF,
    SERVICE_TURN_ON, STATE_CLOSED, STATE_LOCKED, STATE_OFF, STATE_ON,
    STATE_OPEN, STATE_PAUSED, STATE_PLAYING, STATE_UNKNOWN, STATE_UNLOCKED)
from homeassistant.core import State

_LOGGER = logging.getLogger(__name__)


# pylint: disable=too-few-public-methods, attribute-defined-outside-init
class TrackStates(object):
    """
    Records the time when the with-block is entered. Will add all states
    that have changed since the start time to the return list when with-block
    is exited.
    """

    def __init__(self, hass):
        """Initialize a TrackStates block."""
        self.hass = hass
        self.states = []

    def __enter__(self):
        """Record time from which to track changes."""
        self.now = dt_util.utcnow()
        return self.states

    def __exit__(self, exc_type, exc_value, traceback):
        """Add changes states to changes list."""
        self.states.extend(get_changed_since(self.hass.states.all(), self.now))


def get_changed_since(states, utc_point_in_time):
    """List of states that have been changed since utc_point_in_time."""
    point_in_time = dt_util.strip_microseconds(utc_point_in_time)

    return [state for state in states if state.last_updated >= point_in_time]


def reproduce_state(hass, states, blocking=False):
    """Reproduce given state."""
    if isinstance(states, State):
        states = [states]

    to_call = defaultdict(list)

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

        if state.domain == 'group':
            service_domain = 'homeassistant'
        else:
            service_domain = state.domain

        # We group service calls for entities by service call
        # json used to create a hashable version of dict with maybe lists in it
        key = (service_domain, service,
               json.dumps(dict(state.attributes), sort_keys=True))
        to_call[key].append(state.entity_id)

    for (service_domain, service, service_data), entity_ids in to_call.items():
        data = json.loads(service_data)
        data[ATTR_ENTITY_ID] = entity_ids
        hass.services.call(service_domain, service, data, blocking)


def state_as_number(state):
    """Try to coerce our state to a number.

    Raises ValueError if this is not possible.
    """

    if state.state in (STATE_ON, STATE_LOCKED, STATE_ABOVE_HORIZON,
                       STATE_OPEN):
        return 1
    elif state.state in (STATE_OFF, STATE_UNLOCKED, STATE_UNKNOWN,
                         STATE_BELOW_HORIZON, STATE_CLOSED):
        return 0

    return float(state.state)
