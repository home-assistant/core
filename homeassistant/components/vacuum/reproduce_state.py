"""Reproduce an Vacuum state."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
import logging
from typing import Any

from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
)
from homeassistant.core import Context, State
from homeassistant.helpers.typing import HomeAssistantType

from . import (
    ATTR_FAN_SPEED,
    DOMAIN,
    SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_SET_FAN_SPEED,
    SERVICE_START,
    SERVICE_STOP,
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_RETURNING,
)

_LOGGER = logging.getLogger(__name__)

VALID_STATES_TOGGLE = {STATE_ON, STATE_OFF}
VALID_STATES_STATE = {
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_IDLE,
    STATE_RETURNING,
    STATE_PAUSED,
}


async def _async_reproduce_state(
    hass: HomeAssistantType,
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

    if not (state.state in VALID_STATES_TOGGLE or state.state in VALID_STATES_STATE):
        _LOGGER.warning(
            "Invalid state specified for %s: %s", state.entity_id, state.state
        )
        return

    # Return if we are already at the right state.
    if cur_state.state == state.state and cur_state.attributes.get(
        ATTR_FAN_SPEED
    ) == state.attributes.get(ATTR_FAN_SPEED):
        return

    service_data = {ATTR_ENTITY_ID: state.entity_id}

    if cur_state.state != state.state:
        # Wrong state
        if state.state == STATE_ON:
            service = SERVICE_TURN_ON
        elif state.state == STATE_OFF:
            service = SERVICE_TURN_OFF
        elif state.state == STATE_CLEANING:
            service = SERVICE_START
        elif state.state in [STATE_DOCKED, STATE_RETURNING]:
            service = SERVICE_RETURN_TO_BASE
        elif state.state == STATE_IDLE:
            service = SERVICE_STOP
        elif state.state == STATE_PAUSED:
            service = SERVICE_PAUSE

        await hass.services.async_call(
            DOMAIN, service, service_data, context=context, blocking=True
        )

    if cur_state.attributes.get(ATTR_FAN_SPEED) != state.attributes.get(ATTR_FAN_SPEED):
        # Wrong fan speed
        service_data["fan_speed"] = state.attributes[ATTR_FAN_SPEED]
        await hass.services.async_call(
            DOMAIN, SERVICE_SET_FAN_SPEED, service_data, context=context, blocking=True
        )


async def async_reproduce_states(
    hass: HomeAssistantType,
    states: Iterable[State],
    *,
    context: Context | None = None,
    reproduce_options: dict[str, Any] | None = None,
) -> None:
    """Reproduce Vacuum states."""
    # Reproduce states in parallel.
    await asyncio.gather(
        *(
            _async_reproduce_state(
                hass, state, context=context, reproduce_options=reproduce_options
            )
            for state in states
        )
    )
