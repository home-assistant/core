"""Reproduce an Input datetime state."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
import logging
from typing import Any

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import Context, HomeAssistant, State
from homeassistant.util import dt as dt_util

from . import ATTR_DATE, ATTR_DATETIME, ATTR_TIME, CONF_HAS_DATE, CONF_HAS_TIME, DOMAIN

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
    hass: HomeAssistant,
    state: State,
    *,
    context: Context | None = None,
    reproduce_options: dict[str, Any] | None = None,
) -> None:
    """Reproduce a single state."""
    cur_state = hass.states.get(state.entity_id)

    if cur_state is None:
        _LOGGER.warning("Unable to find entity %s", state.entity_id)
        return

    has_time = cur_state.attributes.get(CONF_HAS_TIME)
    has_date = cur_state.attributes.get(CONF_HAS_DATE)

    if not (
        (is_valid_datetime(state.state) and has_date and has_time)
        or (is_valid_date(state.state) and has_date and not has_time)
        or (is_valid_time(state.state) and has_time and not has_date)
    ):
        _LOGGER.warning(
            "Invalid state specified for %s: %s", state.entity_id, state.state
        )
        return

    # Return if we are already at the right state.
    if cur_state.state == state.state:
        return

    service_data = {ATTR_ENTITY_ID: state.entity_id}

    if has_time and has_date:
        service_data[ATTR_DATETIME] = state.state
    elif has_time:
        service_data[ATTR_TIME] = state.state
    elif has_date:
        service_data[ATTR_DATE] = state.state

    await hass.services.async_call(
        DOMAIN, "set_datetime", service_data, context=context, blocking=True
    )


async def async_reproduce_states(
    hass: HomeAssistant,
    states: Iterable[State],
    *,
    context: Context | None = None,
    reproduce_options: dict[str, Any] | None = None,
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
