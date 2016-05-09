"""Helpers that help with state related things."""
import json
import logging
from collections import defaultdict

import homeassistant.util.dt as dt_util
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID, ATTR_MEDIA_CONTENT_TYPE, ATTR_MEDIA_SEEK_POSITION,
    ATTR_MEDIA_VOLUME_LEVEL, ATTR_MEDIA_VOLUME_MUTED, SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOURCE, ATTR_INPUT_SOURCE)
from homeassistant.components.notify import (
    ATTR_MESSAGE, SERVICE_NOTIFY)
from homeassistant.components.sun import (
    STATE_ABOVE_HORIZON, STATE_BELOW_HORIZON)
from homeassistant.components.thermostat import (
    ATTR_AWAY_MODE, ATTR_FAN, SERVICE_SET_AWAY_MODE, SERVICE_SET_FAN_MODE,
    SERVICE_SET_TEMPERATURE)
from homeassistant.components.hvac import (
    ATTR_HUMIDITY, ATTR_SWING_MODE, ATTR_OPERATION_MODE, ATTR_AUX_HEAT,
    SERVICE_SET_HUMIDITY, SERVICE_SET_SWING_MODE,
    SERVICE_SET_OPERATION_MODE, SERVICE_SET_AUX_HEAT)
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_TEMPERATURE, SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_HOME, SERVICE_ALARM_DISARM, SERVICE_ALARM_TRIGGER,
    SERVICE_CLOSE, SERVICE_LOCK, SERVICE_MEDIA_PAUSE, SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_SEEK, SERVICE_MOVE_DOWN, SERVICE_MOVE_UP, SERVICE_OPEN,
    SERVICE_TURN_OFF, SERVICE_TURN_ON, SERVICE_UNLOCK, SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET, STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED, STATE_ALARM_TRIGGERED, STATE_CLOSED, STATE_LOCKED,
    STATE_OFF, STATE_ON, STATE_OPEN, STATE_PAUSED, STATE_PLAYING,
    STATE_UNKNOWN, STATE_UNLOCKED)
from homeassistant.core import State

_LOGGER = logging.getLogger(__name__)

GROUP_DOMAIN = 'group'
HASS_DOMAIN = 'homeassistant'

# Update this dict of lists when new services are added to HA.
# Each item is a service with a list of required attributes.
SERVICE_ATTRIBUTES = {
    SERVICE_PLAY_MEDIA: [ATTR_MEDIA_CONTENT_TYPE, ATTR_MEDIA_CONTENT_ID],
    SERVICE_MEDIA_SEEK: [ATTR_MEDIA_SEEK_POSITION],
    SERVICE_VOLUME_MUTE: [ATTR_MEDIA_VOLUME_MUTED],
    SERVICE_VOLUME_SET: [ATTR_MEDIA_VOLUME_LEVEL],
    SERVICE_NOTIFY: [ATTR_MESSAGE],
    SERVICE_SET_AWAY_MODE: [ATTR_AWAY_MODE],
    SERVICE_SET_FAN_MODE: [ATTR_FAN],
    SERVICE_SET_TEMPERATURE: [ATTR_TEMPERATURE],
    SERVICE_SET_HUMIDITY: [ATTR_HUMIDITY],
    SERVICE_SET_SWING_MODE: [ATTR_SWING_MODE],
    SERVICE_SET_OPERATION_MODE: [ATTR_OPERATION_MODE],
    SERVICE_SET_AUX_HEAT: [ATTR_AUX_HEAT],
    SERVICE_SELECT_SOURCE: [ATTR_INPUT_SOURCE],
}

# Update this dict when new services are added to HA.
# Each item is a service with a corresponding state.
SERVICE_TO_STATE = {
    SERVICE_TURN_ON: STATE_ON,
    SERVICE_TURN_OFF: STATE_OFF,
    SERVICE_MEDIA_PLAY: STATE_PLAYING,
    SERVICE_MEDIA_PAUSE: STATE_PAUSED,
    SERVICE_ALARM_ARM_AWAY: STATE_ALARM_ARMED_AWAY,
    SERVICE_ALARM_ARM_HOME: STATE_ALARM_ARMED_HOME,
    SERVICE_ALARM_DISARM: STATE_ALARM_DISARMED,
    SERVICE_ALARM_TRIGGER: STATE_ALARM_TRIGGERED,
    SERVICE_LOCK: STATE_LOCKED,
    SERVICE_UNLOCK: STATE_UNLOCKED,
    SERVICE_CLOSE: STATE_CLOSED,
    SERVICE_OPEN: STATE_OPEN,
    SERVICE_MOVE_UP: STATE_OPEN,
    SERVICE_MOVE_DOWN: STATE_CLOSED,
}


# pylint: disable=too-few-public-methods, attribute-defined-outside-init
class TrackStates(object):
    """
    Record the time when the with-block is entered.

    Add all states that have changed since the start time to the return list
    when with-block is exited.
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
    """Return list of states that have been changed since utc_point_in_time."""
    return [state for state in states
            if state.last_updated >= utc_point_in_time]


def reproduce_state(hass, states, blocking=False):
    """Reproduce given state."""
    if isinstance(states, State):
        states = [states]

    to_call = defaultdict(list)

    for state in states:

        if hass.states.get(state.entity_id) is None:
            _LOGGER.warning('reproduce_state: Unable to find entity %s',
                            state.entity_id)
            continue

        if state.domain == GROUP_DOMAIN:
            service_domain = HASS_DOMAIN
        else:
            service_domain = state.domain

        domain_services = hass.services.services[service_domain]

        service = None
        for _service in domain_services.keys():
            if (_service in SERVICE_ATTRIBUTES and
                    all(attr in state.attributes
                        for attr in SERVICE_ATTRIBUTES[_service]) or
                    _service in SERVICE_TO_STATE and
                    SERVICE_TO_STATE[_service] == state.state):
                service = _service
            if (_service in SERVICE_TO_STATE and
                    SERVICE_TO_STATE[_service] == state.state):
                break

        if not service:
            _LOGGER.warning("reproduce_state: Unable to reproduce state %s",
                            state)
            continue

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
    """
    Try to coerce our state to a number.

    Raises ValueError if this is not possible.
    """
    if state.state in (STATE_ON, STATE_LOCKED, STATE_ABOVE_HORIZON,
                       STATE_OPEN):
        return 1
    elif state.state in (STATE_OFF, STATE_UNLOCKED, STATE_UNKNOWN,
                         STATE_BELOW_HORIZON, STATE_CLOSED):
        return 0

    return float(state.state)
