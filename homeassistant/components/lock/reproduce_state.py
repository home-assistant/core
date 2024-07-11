"""Reproduce an Lock state."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
import logging
from typing import Any

from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_LOCK,
    SERVICE_OPEN,
    SERVICE_UNLOCK,
    STATE_LOCKED,
    STATE_LOCKING,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNLOCKED,
    STATE_UNLOCKING,
)
from homeassistant.core import Context, HomeAssistant, State

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

VALID_STATES = {
    STATE_LOCKED,
    STATE_LOCKING,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNLOCKED,
    STATE_UNLOCKING,
}


async def _async_reproduce_state(
    hass: HomeAssistant,
    state: State,
    *,
    context: Context | None = None,
    reproduce_options: dict[str, Any] | None = None,
) -> None:
    """Reproduce a single state."""
    if (cur_state := hass.states.get(state.entity_id)) is None:
        _LOGGER.warning("Unable to find entity %s", state.entity_id)
        return

    if state.state not in VALID_STATES:
        _LOGGER.warning(
            "Invalid state specified for %s: %s", state.entity_id, state.state
        )
        return

    # Return if we are already at the right state.
    if cur_state.state == state.state:
        return

    service_data = {ATTR_ENTITY_ID: state.entity_id}

    if state.state in {STATE_LOCKED, STATE_LOCKING}:
        service = SERVICE_LOCK
    elif state.state in {STATE_UNLOCKED, STATE_UNLOCKING}:
        service = SERVICE_UNLOCK
    elif state.state in {STATE_OPEN, STATE_OPENING}:
        service = SERVICE_OPEN

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
    """Reproduce Lock states."""
    await asyncio.gather(
        *(
            _async_reproduce_state(
                hass, state, context=context, reproduce_options=reproduce_options
            )
            for state in states
        )
    )
