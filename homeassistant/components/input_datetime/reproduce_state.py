"""Reproduce an Input datetime state."""
import asyncio
import logging
from typing import Any, Dict, Iterable, Optional

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import Context, State
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import dt as dt_util

from . import (
    ATTR_DATE,
    ATTR_DATETIME,
    ATTR_TIME,
    CONF_HAS_DATE,
    CONF_HAS_TIME,
    DOMAIN,
    SERVICE_SET_DATETIME,
)

_LOGGER = logging.getLogger(__name__)


def is_valid_datetime(string: str) -> bool:
    """Test if string dt is a valid datetime."""
    try:
        return dt_util.parse_datetime(string) is not None
    except ValueError:
        return False


def is_valid_date(string: str) -> bool:
    """Test if string dt is a valid date."""
    return dt_util.parse_date(string) is not None


def is_valid_time(string: str) -> bool:
    """Test if string dt is a valid time."""
    return dt_util.parse_time(string) is not None


async def _async_reproduce_state(
    hass: HomeAssistantType,
    state: State,
    *,
    context: Optional[Context] = None,
    reproduce_options: Optional[Dict[str, Any]] = None,
) -> None:
    """Reproduce a single state."""
    cur_state = hass.states.get(state.entity_id)

    if cur_state is None:
        _LOGGER.warning("Unable to find entity %s", state.entity_id)
        return

    if not (
        (
            is_valid_datetime(state.state)
            and cur_state.attributes.get(CONF_HAS_DATE)
            and cur_state.attributes.get(CONF_HAS_TIME)
        )
        or (
            is_valid_date(state.state)
            and cur_state.attributes.get(CONF_HAS_DATE)
            and not cur_state.attributes.get(CONF_HAS_TIME)
        )
        or (
            is_valid_time(state.state)
            and cur_state.attributes.get(CONF_HAS_TIME)
            and not cur_state.attributes.get(CONF_HAS_DATE)
        )
    ):
        _LOGGER.warning(
            "Invalid state specified for %s: %s", state.entity_id, state.state
        )
        return

    # Return if we are already at the right state.
    if cur_state.state == state.state:
        return

    service = SERVICE_SET_DATETIME
    service_data = {ATTR_ENTITY_ID: state.entity_id}

    has_time = cur_state.attributes.get(CONF_HAS_TIME)
    has_date = cur_state.attributes.get(CONF_HAS_DATE)

    if has_time and has_date:
        service_data[ATTR_DATETIME] = state.state
    elif has_time:
        service_data[ATTR_TIME] = state.state
    elif has_date:
        service_data[ATTR_DATE] = state.state
    else:
        _LOGGER.warning("input_datetime needs either has_date or has_time or both")
        return

    await hass.services.async_call(
        DOMAIN, service, service_data, context=context, blocking=True
    )


async def async_reproduce_states(
    hass: HomeAssistantType,
    states: Iterable[State],
    *,
    context: Optional[Context] = None,
    reproduce_options: Optional[Dict[str, Any]] = None,
) -> None:
    """Reproduce Input datetime states."""
    await asyncio.gather(
        *(
            _async_reproduce_state(
                hass, state, context=context, reproduce_options=reproduce_options
            )
            for state in states
        )
    )
