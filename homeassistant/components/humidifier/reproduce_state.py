"""Module that groups code required to handle state restore for component."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
import logging
from typing import Any

from homeassistant.const import (
    ATTR_MODE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import Context, HomeAssistant, State

from .const import ATTR_HUMIDITY, DOMAIN, SERVICE_SET_HUMIDITY, SERVICE_SET_MODE

_LOGGER = logging.getLogger(__name__)


async def _async_reproduce_states(
    hass: HomeAssistant,
    state: State,
    *,
    context: Context | None = None,
    reproduce_options: dict[str, Any] | None = None,
) -> None:
    """Reproduce component states."""
    cur_state = hass.states.get(state.entity_id)

    if cur_state is None:
        _LOGGER.warning("Unable to find entity %s", state.entity_id)
        return

    async def call_service(service: str, keys: Iterable, data=None):
        """Call service with set of attributes given."""
        data = data or {}
        data["entity_id"] = state.entity_id
        for key in keys:
            if key in state.attributes:
                data[key] = state.attributes[key]

        await hass.services.async_call(
            DOMAIN, service, data, blocking=True, context=context
        )

    if state.state == STATE_OFF:
        # Ensure the device is off if it needs to be and exit
        if cur_state.state != STATE_OFF:
            await call_service(SERVICE_TURN_OFF, [])
        return

    if state.state != STATE_ON:
        # we can't know how to handle this
        _LOGGER.warning(
            "Invalid state specified for %s: %s", state.entity_id, state.state
        )
        return

    # First of all, turn on if needed, because the device might not
    # be able to set mode and humidity while being off
    if cur_state.state != STATE_ON:
        await call_service(SERVICE_TURN_ON, [])
        # refetch the state as turning on might allow us to see some more values
        cur_state = hass.states.get(state.entity_id)

    # Then set the mode before target humidity, because switching modes
    # may invalidate target humidity
    if ATTR_MODE in state.attributes and state.attributes[
        ATTR_MODE
    ] != cur_state.attributes.get(ATTR_MODE):
        await call_service(SERVICE_SET_MODE, [ATTR_MODE])

    # Next, restore target humidity for the current mode
    if ATTR_HUMIDITY in state.attributes and state.attributes[
        ATTR_HUMIDITY
    ] != cur_state.attributes.get(ATTR_HUMIDITY):
        await call_service(SERVICE_SET_HUMIDITY, [ATTR_HUMIDITY])


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
