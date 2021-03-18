"""Reproduce an Water heater state."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Iterable

from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import Context, State
from homeassistant.helpers.typing import HomeAssistantType

from . import (
    ATTR_AWAY_MODE,
    ATTR_OPERATION_MODE,
    ATTR_TEMPERATURE,
    DOMAIN,
    SERVICE_SET_AWAY_MODE,
    SERVICE_SET_OPERATION_MODE,
    SERVICE_SET_TEMPERATURE,
    STATE_ECO,
    STATE_ELECTRIC,
    STATE_GAS,
    STATE_HEAT_PUMP,
    STATE_HIGH_DEMAND,
    STATE_PERFORMANCE,
)

_LOGGER = logging.getLogger(__name__)

VALID_STATES = {
    STATE_ECO,
    STATE_ELECTRIC,
    STATE_GAS,
    STATE_HEAT_PUMP,
    STATE_HIGH_DEMAND,
    STATE_OFF,
    STATE_ON,
    STATE_PERFORMANCE,
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

    if state.state not in VALID_STATES:
        _LOGGER.warning(
            "Invalid state specified for %s: %s", state.entity_id, state.state
        )
        return

    # Return if we are already at the right state.
    if (
        cur_state.state == state.state
        and cur_state.attributes.get(ATTR_TEMPERATURE)
        == state.attributes.get(ATTR_TEMPERATURE)
        and cur_state.attributes.get(ATTR_AWAY_MODE)
        == state.attributes.get(ATTR_AWAY_MODE)
    ):
        return

    service_data = {ATTR_ENTITY_ID: state.entity_id}

    if state.state != cur_state.state:
        if state.state == STATE_ON:
            service = SERVICE_TURN_ON
        elif state.state == STATE_OFF:
            service = SERVICE_TURN_OFF
        else:
            service = SERVICE_SET_OPERATION_MODE
            service_data[ATTR_OPERATION_MODE] = state.state

        await hass.services.async_call(
            DOMAIN, service, service_data, context=context, blocking=True
        )

    if (
        state.attributes.get(ATTR_TEMPERATURE)
        != cur_state.attributes.get(ATTR_TEMPERATURE)
        and state.attributes.get(ATTR_TEMPERATURE) is not None
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: state.entity_id,
                ATTR_TEMPERATURE: state.attributes.get(ATTR_TEMPERATURE),
            },
            context=context,
            blocking=True,
        )

    if (
        state.attributes.get(ATTR_AWAY_MODE) != cur_state.attributes.get(ATTR_AWAY_MODE)
        and state.attributes.get(ATTR_AWAY_MODE) is not None
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_AWAY_MODE,
            {
                ATTR_ENTITY_ID: state.entity_id,
                ATTR_AWAY_MODE: state.attributes.get(ATTR_AWAY_MODE),
            },
            context=context,
            blocking=True,
        )


async def async_reproduce_states(
    hass: HomeAssistantType,
    states: Iterable[State],
    *,
    context: Context | None = None,
    reproduce_options: dict[str, Any] | None = None,
) -> None:
    """Reproduce Water heater states."""
    await asyncio.gather(
        *(
            _async_reproduce_state(
                hass, state, context=context, reproduce_options=reproduce_options
            )
            for state in states
        )
    )
