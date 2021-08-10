"""Reproduce an Input text state."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
import logging
from typing import Any

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import Context, HomeAssistant, State

from . import ATTR_VALUE, DOMAIN, SERVICE_SET_VALUE

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

    # Return if we can't find the entity
    if cur_state is None:
        _LOGGER.warning("Unable to find entity %s", state.entity_id)
        return

    # Return if we are already at the right state.
    if cur_state.state == state.state:
        return

    # Call service
    service = SERVICE_SET_VALUE
    service_data = {ATTR_ENTITY_ID: state.entity_id, ATTR_VALUE: state.state}

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
    """Reproduce Input text states."""
    # Reproduce states in parallel.
    await asyncio.gather(
        *(
            _async_reproduce_state(
                hass, state, context=context, reproduce_options=reproduce_options
            )
            for state in states
        )
    )
