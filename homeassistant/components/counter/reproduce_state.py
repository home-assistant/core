"""Reproduce an Counter state."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Iterable

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import Context, HomeAssistant, State

from . import (
    ATTR_INITIAL,
    ATTR_MAXIMUM,
    ATTR_MINIMUM,
    ATTR_STEP,
    DOMAIN,
    SERVICE_CONFIGURE,
    VALUE,
)

_LOGGER = logging.getLogger(__name__)


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

    if not state.state.isdigit():
        _LOGGER.warning(
            "Invalid state specified for %s: %s", state.entity_id, state.state
        )
        return

    # Return if we are already at the right state.
    if (
        cur_state.state == state.state
        and cur_state.attributes.get(ATTR_INITIAL) == state.attributes.get(ATTR_INITIAL)
        and cur_state.attributes.get(ATTR_MAXIMUM) == state.attributes.get(ATTR_MAXIMUM)
        and cur_state.attributes.get(ATTR_MINIMUM) == state.attributes.get(ATTR_MINIMUM)
        and cur_state.attributes.get(ATTR_STEP) == state.attributes.get(ATTR_STEP)
    ):
        return

    service_data = {ATTR_ENTITY_ID: state.entity_id, VALUE: state.state}
    service = SERVICE_CONFIGURE
    if ATTR_INITIAL in state.attributes:
        service_data[ATTR_INITIAL] = state.attributes[ATTR_INITIAL]
    if ATTR_MAXIMUM in state.attributes:
        service_data[ATTR_MAXIMUM] = state.attributes[ATTR_MAXIMUM]
    if ATTR_MINIMUM in state.attributes:
        service_data[ATTR_MINIMUM] = state.attributes[ATTR_MINIMUM]
    if ATTR_STEP in state.attributes:
        service_data[ATTR_STEP] = state.attributes[ATTR_STEP]

    await hass.services.async_call(
        DOMAIN, service, service_data, context=context, blocking=True
    )


async def async_reproduce_states(
    hass: HomeAssistant,
    states: Iterable[State],
    *,
    context: Context | None = None,
    reproduce_options: dict[str, Any] | None = None,
) -> None:
    """Reproduce Counter states."""
    await asyncio.gather(
        *(
            _async_reproduce_state(
                hass, state, context=context, reproduce_options=reproduce_options
            )
            for state in states
        )
    )
