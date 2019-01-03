"""Helpers that help with state related things."""
import asyncio
import datetime as dt
import json
import logging
from collections import defaultdict
from types import TracebackType
from typing import (  # noqa: F401 pylint: disable=unused-import
    Awaitable, Dict, Iterable, List, Optional, Tuple, Type, Union)

from homeassistant.loader import bind_hass
import homeassistant.util.dt as dt_util
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID, ATTR_MEDIA_CONTENT_TYPE, ATTR_MEDIA_SEEK_POSITION,
    ATTR_MEDIA_VOLUME_LEVEL, ATTR_MEDIA_VOLUME_MUTED, SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOURCE, ATTR_INPUT_SOURCE)
from homeassistant.components.notify import (
    ATTR_MESSAGE, SERVICE_NOTIFY)
from homeassistant.components.sun import (
    STATE_ABOVE_HORIZON, STATE_BELOW_HORIZON)
from homeassistant.components.switch.mysensors import (
    ATTR_IR_CODE, SERVICE_SEND_IR_CODE)
from homeassistant.components.climate import (
    ATTR_AUX_HEAT, ATTR_AWAY_MODE, ATTR_FAN_MODE, ATTR_HOLD_MODE,
    ATTR_HUMIDITY, ATTR_OPERATION_MODE, ATTR_SWING_MODE,
    SERVICE_SET_AUX_HEAT, SERVICE_SET_AWAY_MODE, SERVICE_SET_HOLD_MODE,
    SERVICE_SET_FAN_MODE, SERVICE_SET_HUMIDITY, SERVICE_SET_OPERATION_MODE,
    SERVICE_SET_SWING_MODE, SERVICE_SET_TEMPERATURE, STATE_HEAT, STATE_COOL,
    STATE_IDLE)
from homeassistant.components.climate.ecobee import (
    ATTR_FAN_MIN_ON_TIME, SERVICE_SET_FAN_MIN_ON_TIME,
    ATTR_RESUME_ALL, SERVICE_RESUME_PROGRAM)
from homeassistant.components.cover import (
    ATTR_POSITION, ATTR_TILT_POSITION)
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_OPTION, ATTR_TEMPERATURE, SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_HOME, SERVICE_ALARM_DISARM, SERVICE_ALARM_TRIGGER,
    SERVICE_LOCK, SERVICE_MEDIA_PAUSE, SERVICE_MEDIA_PLAY, SERVICE_MEDIA_STOP,
    SERVICE_MEDIA_SEEK, SERVICE_TURN_OFF, SERVICE_TURN_ON, SERVICE_UNLOCK,
    SERVICE_VOLUME_MUTE, SERVICE_VOLUME_SET, SERVICE_OPEN_COVER,
    SERVICE_CLOSE_COVER, SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION, STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED, STATE_ALARM_TRIGGERED,
    STATE_CLOSED, STATE_HOME, STATE_LOCKED, STATE_NOT_HOME, STATE_OFF,
    STATE_ON, STATE_OPEN, STATE_PAUSED, STATE_PLAYING, STATE_UNKNOWN,
    STATE_UNLOCKED, SERVICE_SELECT_OPTION)
from homeassistant.core import State, DOMAIN as HASS_DOMAIN
from homeassistant.util.async_ import run_coroutine_threadsafe
from .typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)

GROUP_DOMAIN = 'group'

# Update this dict of lists when new services are added to HA.
# Each item is a service with a list of required attributes.
SERVICE_ATTRIBUTES = {
    SERVICE_PLAY_MEDIA: [ATTR_MEDIA_CONTENT_TYPE, ATTR_MEDIA_CONTENT_ID],
    SERVICE_MEDIA_SEEK: [ATTR_MEDIA_SEEK_POSITION],
    SERVICE_VOLUME_MUTE: [ATTR_MEDIA_VOLUME_MUTED],
    SERVICE_VOLUME_SET: [ATTR_MEDIA_VOLUME_LEVEL],
    SERVICE_NOTIFY: [ATTR_MESSAGE],
    SERVICE_SET_AWAY_MODE: [ATTR_AWAY_MODE],
    SERVICE_SET_FAN_MODE: [ATTR_FAN_MODE],
    SERVICE_SET_FAN_MIN_ON_TIME: [ATTR_FAN_MIN_ON_TIME],
    SERVICE_RESUME_PROGRAM: [ATTR_RESUME_ALL],
    SERVICE_SET_TEMPERATURE: [ATTR_TEMPERATURE],
    SERVICE_SET_HUMIDITY: [ATTR_HUMIDITY],
    SERVICE_SET_SWING_MODE: [ATTR_SWING_MODE],
    SERVICE_SET_HOLD_MODE: [ATTR_HOLD_MODE],
    SERVICE_SET_OPERATION_MODE: [ATTR_OPERATION_MODE],
    SERVICE_SET_AUX_HEAT: [ATTR_AUX_HEAT],
    SERVICE_SELECT_SOURCE: [ATTR_INPUT_SOURCE],
    SERVICE_SEND_IR_CODE: [ATTR_IR_CODE],
    SERVICE_SELECT_OPTION: [ATTR_OPTION],
    SERVICE_SET_COVER_POSITION: [ATTR_POSITION],
    SERVICE_SET_COVER_TILT_POSITION: [ATTR_TILT_POSITION]
}

# Update this dict when new services are added to HA.
# Each item is a service with a corresponding state.
SERVICE_TO_STATE = {
    SERVICE_TURN_ON: STATE_ON,
    SERVICE_TURN_OFF: STATE_OFF,
    SERVICE_MEDIA_PLAY: STATE_PLAYING,
    SERVICE_MEDIA_PAUSE: STATE_PAUSED,
    SERVICE_MEDIA_STOP: STATE_IDLE,
    SERVICE_ALARM_ARM_AWAY: STATE_ALARM_ARMED_AWAY,
    SERVICE_ALARM_ARM_HOME: STATE_ALARM_ARMED_HOME,
    SERVICE_ALARM_DISARM: STATE_ALARM_DISARMED,
    SERVICE_ALARM_TRIGGER: STATE_ALARM_TRIGGERED,
    SERVICE_LOCK: STATE_LOCKED,
    SERVICE_UNLOCK: STATE_UNLOCKED,
    SERVICE_OPEN_COVER: STATE_OPEN,
    SERVICE_CLOSE_COVER: STATE_CLOSED
}


class AsyncTrackStates:
    """
    Record the time when the with-block is entered.

    Add all states that have changed since the start time to the return list
    when with-block is exited.

    Must be run within the event loop.
    """

    def __init__(self, hass: HomeAssistantType) -> None:
        """Initialize a TrackStates block."""
        self.hass = hass
        self.states = []  # type: List[State]

    # pylint: disable=attribute-defined-outside-init
    def __enter__(self) -> List[State]:
        """Record time from which to track changes."""
        self.now = dt_util.utcnow()
        return self.states

    def __exit__(self, exc_type: Optional[Type[BaseException]],
                 exc_value: Optional[BaseException],
                 traceback: Optional[TracebackType]) -> None:
        """Add changes states to changes list."""
        self.states.extend(get_changed_since(self.hass.states.async_all(),
                                             self.now))


def get_changed_since(states: Iterable[State],
                      utc_point_in_time: dt.datetime) -> List[State]:
    """Return list of states that have been changed since utc_point_in_time."""
    return [state for state in states
            if state.last_updated >= utc_point_in_time]


@bind_hass
def reproduce_state(hass: HomeAssistantType,
                    states: Union[State, Iterable[State]],
                    blocking: bool = False) -> None:
    """Reproduce given state."""
    return run_coroutine_threadsafe(  # type: ignore
        async_reproduce_state(hass, states, blocking), hass.loop).result()


@bind_hass
async def async_reproduce_state(hass: HomeAssistantType,
                                states: Union[State, Iterable[State]],
                                blocking: bool = False) -> None:
    """Reproduce given state."""
    if isinstance(states, State):
        states = [states]

    to_call = defaultdict(list)  # type: Dict[Tuple[str, str, str], List[str]]

    for state in states:

        if hass.states.get(state.entity_id) is None:
            _LOGGER.warning("reproduce_state: Unable to find entity %s",
                            state.entity_id)
            continue

        if state.domain == GROUP_DOMAIN:
            service_domain = HASS_DOMAIN
        else:
            service_domain = state.domain

        domain_services = hass.services.async_services().get(service_domain)

        if not domain_services:
            _LOGGER.warning(
                "reproduce_state: Unable to reproduce state %s (1)", state)
            continue

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
            _LOGGER.warning(
                "reproduce_state: Unable to reproduce state %s (2)", state)
            continue

        # We group service calls for entities by service call
        # json used to create a hashable version of dict with maybe lists in it
        key = (service_domain, service,
               json.dumps(dict(state.attributes), sort_keys=True))
        to_call[key].append(state.entity_id)

    domain_tasks = {}  # type: Dict[str, List[Awaitable[Optional[bool]]]]
    for (service_domain, service, service_data), entity_ids in to_call.items():
        data = json.loads(service_data)
        data[ATTR_ENTITY_ID] = entity_ids

        if service_domain not in domain_tasks:
            domain_tasks[service_domain] = []

        domain_tasks[service_domain].append(
            hass.services.async_call(service_domain, service, data, blocking)
        )

    async def async_handle_service_calls(
            coro_list: Iterable[Awaitable]) -> None:
        """Handle service calls by domain sequence."""
        for coro in coro_list:
            await coro

    execute_tasks = [async_handle_service_calls(coro_list)
                     for coro_list in domain_tasks.values()]
    if execute_tasks:
        await asyncio.wait(execute_tasks, loop=hass.loop)


def state_as_number(state: State) -> float:
    """
    Try to coerce our state to a number.

    Raises ValueError if this is not possible.
    """
    if state.state in (STATE_ON, STATE_LOCKED, STATE_ABOVE_HORIZON,
                       STATE_OPEN, STATE_HOME, STATE_HEAT, STATE_COOL):
        return 1
    if state.state in (STATE_OFF, STATE_UNLOCKED, STATE_UNKNOWN,
                       STATE_BELOW_HORIZON, STATE_CLOSED, STATE_NOT_HOME,
                       STATE_IDLE):
        return 0

    return float(state.state)
