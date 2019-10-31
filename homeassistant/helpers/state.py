"""Helpers that help with state related things."""
import asyncio
import datetime as dt
import json
import logging
from collections import defaultdict
from types import ModuleType, TracebackType
from typing import Awaitable, Dict, Iterable, List, Optional, Tuple, Type, Union

from homeassistant.loader import bind_hass, async_get_integration, IntegrationNotFound
import homeassistant.util.dt as dt_util
from homeassistant.components.notify import ATTR_MESSAGE, SERVICE_NOTIFY
from homeassistant.components.sun import STATE_ABOVE_HORIZON, STATE_BELOW_HORIZON
from homeassistant.components.cover import ATTR_POSITION, ATTR_TILT_POSITION
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_DISARM,
    SERVICE_ALARM_TRIGGER,
    SERVICE_LOCK,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_UNLOCK,
    SERVICE_OPEN_COVER,
    SERVICE_CLOSE_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
    STATE_CLOSED,
    STATE_HOME,
    STATE_LOCKED,
    STATE_NOT_HOME,
    STATE_OFF,
    STATE_ON,
    STATE_OPEN,
    STATE_UNKNOWN,
    STATE_UNLOCKED,
)
from homeassistant.core import Context, State, DOMAIN as HASS_DOMAIN
from .typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)

GROUP_DOMAIN = "group"

# Update this dict of lists when new services are added to HA.
# Each item is a service with a list of required attributes.
SERVICE_ATTRIBUTES = {
    SERVICE_NOTIFY: [ATTR_MESSAGE],
    SERVICE_SET_COVER_POSITION: [ATTR_POSITION],
    SERVICE_SET_COVER_TILT_POSITION: [ATTR_TILT_POSITION],
}

# Update this dict when new services are added to HA.
# Each item is a service corresponding to the key state.
SERVICE_BY_TARGET_STATE = {
    STATE_ON: SERVICE_TURN_ON,
    STATE_OFF: SERVICE_TURN_OFF,
    STATE_ALARM_ARMED_AWAY: SERVICE_ALARM_ARM_AWAY,
    STATE_ALARM_ARMED_HOME: SERVICE_ALARM_ARM_HOME,
    STATE_ALARM_DISARMED: SERVICE_ALARM_DISARM,
    STATE_ALARM_TRIGGERED: SERVICE_ALARM_TRIGGER,
    STATE_LOCKED: SERVICE_LOCK,
    STATE_UNLOCKED: SERVICE_UNLOCK,
    STATE_OPEN: SERVICE_OPEN_COVER,
    STATE_CLOSED: SERVICE_CLOSE_COVER,
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
        self.states: List[State] = []

    # pylint: disable=attribute-defined-outside-init
    def __enter__(self) -> List[State]:
        """Record time from which to track changes."""
        self.now = dt_util.utcnow()
        return self.states

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        """Add changes states to changes list."""
        self.states.extend(get_changed_since(self.hass.states.async_all(), self.now))


def get_changed_since(
    states: Iterable[State], utc_point_in_time: dt.datetime
) -> List[State]:
    """Return list of states that have been changed since utc_point_in_time."""
    return [state for state in states if state.last_updated >= utc_point_in_time]


@bind_hass
def reproduce_state(
    hass: HomeAssistantType,
    states: Union[State, Iterable[State]],
    blocking: bool = False,
) -> None:
    """Reproduce given state."""
    return asyncio.run_coroutine_threadsafe(
        async_reproduce_state(hass, states, blocking), hass.loop
    ).result()


@bind_hass
async def async_reproduce_state(
    hass: HomeAssistantType,
    states: Union[State, Iterable[State]],
    blocking: bool = False,
    context: Optional[Context] = None,
) -> None:
    """Reproduce a list of states on multiple domains."""
    if isinstance(states, State):
        states = [states]

    to_call: Dict[str, List[State]] = defaultdict(list)

    for state in states:
        to_call[state.domain].append(state)

    async def worker(domain: str, states_by_domain: List[State]) -> None:
        try:
            integration = await async_get_integration(hass, domain)
        except IntegrationNotFound:
            _LOGGER.warning(
                "Trying to reproduce state for unknown integration: %s", domain
            )
            return

        try:
            platform: Optional[ModuleType] = integration.get_platform("reproduce_state")
        except ImportError:
            platform = None

        if platform:
            await platform.async_reproduce_states(  # type: ignore
                hass, states_by_domain, context=context
            )
        else:
            await async_reproduce_state_legacy(
                hass, domain, states_by_domain, blocking=blocking, context=context
            )

    if to_call:
        # run all domains in parallel
        await asyncio.gather(
            *(worker(domain, data) for domain, data in to_call.items())
        )


@bind_hass
def find_service_for_state(
    hass: HomeAssistantType, service_domain: str, state: State
) -> Optional[str]:
    """Find the service needed to reproduce the given state."""
    domain_services = hass.services.async_services().get(service_domain)

    if not domain_services:
        _LOGGER.warning("reproduce_state: Unable to reproduce state %s (1)", state)
        return None

    if state.state in SERVICE_BY_TARGET_STATE and state.state in domain_services:
        return state.state

    for _service in domain_services:
        if _service in SERVICE_ATTRIBUTES and all(
            attr in state.attributes for attr in SERVICE_ATTRIBUTES[_service]
        ):
            return _service


@bind_hass
async def async_reproduce_state_legacy(
    hass: HomeAssistantType,
    domain: str,
    states: Iterable[State],
    blocking: bool = False,
    context: Optional[Context] = None,
) -> None:
    """Reproduce given state."""
    to_call: Dict[Tuple[str, str], List[str]] = defaultdict(list)

    if domain == GROUP_DOMAIN:
        service_domain = HASS_DOMAIN
    else:
        service_domain = domain

    for state in states:

        if hass.states.get(state.entity_id) is None:
            _LOGGER.warning(
                "reproduce_state: Unable to find entity %s", state.entity_id
            )
            continue

        domain_services = hass.services.async_services().get(service_domain)

        if not domain_services:
            _LOGGER.warning("reproduce_state: Unable to reproduce state %s (1)", state)
            continue

        service = find_service_for_state(hass, service_domain, state)

        if not service:
            _LOGGER.warning("reproduce_state: Unable to reproduce state %s (2)", state)
            continue

        # We group service calls for entities by service call
        # json used to create a hashable version of dict with maybe lists in it
        key = (service, json.dumps(dict(state.attributes), sort_keys=True))
        to_call[key].append(state.entity_id)

    domain_tasks: List[Awaitable[Optional[bool]]] = []
    for (service, service_data), entity_ids in to_call.items():
        data = json.loads(service_data)
        data[ATTR_ENTITY_ID] = entity_ids

        domain_tasks.append(
            hass.services.async_call(service_domain, service, data, blocking, context)
        )

    if domain_tasks:
        await asyncio.wait(domain_tasks)


def state_as_number(state: State) -> float:
    """
    Try to coerce our state to a number.

    Raises ValueError if this is not possible.
    """
    if state.state in (
        STATE_ON,
        STATE_LOCKED,
        STATE_ABOVE_HORIZON,
        STATE_OPEN,
        STATE_HOME,
    ):
        return 1
    if state.state in (
        STATE_OFF,
        STATE_UNLOCKED,
        STATE_UNKNOWN,
        STATE_BELOW_HORIZON,
        STATE_CLOSED,
        STATE_NOT_HOME,
    ):
        return 0

    return float(state.state)
