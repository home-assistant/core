"""Reproduce an Timer state."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
import logging
from typing import Any

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import Context, HomeAssistant, State

from . import (
    ATTR_DURATION,
    DOMAIN,
    SERVICE_CANCEL,
    SERVICE_PAUSE,
    SERVICE_START,
    STATUS_ACTIVE,
    STATUS_IDLE,
    STATUS_PAUSED,
)

_LOGGER = logging.getLogger(__name__)

VALID_STATES = {STATUS_IDLE, STATUS_ACTIVE, STATUS_PAUSED}


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
    if cur_state.state == state.state and cur_state.attributes.get(
        ATTR_DURATION
    ) == state.attributes.get(ATTR_DURATION):
        return

    service_data = {ATTR_ENTITY_ID: state.entity_id}

    if state.state == STATUS_ACTIVE:
        service = SERVICE_START
        if ATTR_DURATION in state.attributes:
            service_data[ATTR_DURATION] = state.attributes[ATTR_DURATION]
    elif state.state == STATUS_PAUSED:
        service = SERVICE_PAUSE
    elif state.state == STATUS_IDLE:
        service = SERVICE_CANCEL

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
    """Reproduce Timer states."""
    await asyncio.gather(
        *(
            _async_reproduce_state(
                hass, state, context=context, reproduce_options=reproduce_options
            )
            for state in states
        )
    )
