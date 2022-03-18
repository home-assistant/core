"""Reproduce an input boolean state."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
import logging
from typing import Any

from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import Context, HomeAssistant, State

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def _async_reproduce_states(
    hass: HomeAssistant,
    state: State,
    *,
    context: Context | None = None,
    reproduce_options: dict[str, Any] | None = None,
) -> None:
    """Reproduce input boolean states."""
    if (cur_state := hass.states.get(state.entity_id)) is None:
        _LOGGER.warning("Unable to find entity %s", state.entity_id)
        return

    if state.state not in (STATE_ON, STATE_OFF):
        _LOGGER.warning(
            "Invalid state specified for %s: %s", state.entity_id, state.state
        )
        return

    if cur_state.state == state.state:
        return

    service = SERVICE_TURN_ON if state.state == STATE_ON else SERVICE_TURN_OFF

    await hass.services.async_call(
        DOMAIN,
        service,
        {ATTR_ENTITY_ID: state.entity_id},
        context=context,
        blocking=True,
    )


async def async_reproduce_states(
    hass: HomeAssistant,
    states: Iterable[State],
    *,
    context: Context | None = None,
    reproduce_options: dict[str, Any] | None = None,
) -> None:
    """Reproduce component states."""
    await asyncio.gather(
        *(
            _async_reproduce_states(
                hass, state, context=context, reproduce_options=reproduce_options
            )
            for state in states
        )
    )
