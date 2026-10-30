"""Reproduce an Water heater state."""

import asyncio
from collections.abc import Iterable
import logging
from typing import Any

from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import Context, HomeAssistant, State

from . import (
    STATE_ECO,
    STATE_ELECTRIC,
    STATE_GAS,
    STATE_HEAT_PUMP,
    STATE_HIGH_DEMAND,
    STATE_PERFORMANCE,
)
from .const import (
    DOMAIN,
    WaterHeaterService,
    WaterHeaterServiceArgument,
    WaterHeaterStateAttribute,
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
    if (
        cur_state.state == state.state
        and cur_state.attributes.get(WaterHeaterStateAttribute.TARGET_TEMPERATURE)
        == state.attributes.get(WaterHeaterStateAttribute.TARGET_TEMPERATURE)
        and cur_state.attributes.get(WaterHeaterStateAttribute.AWAY_MODE)
        == state.attributes.get(WaterHeaterStateAttribute.AWAY_MODE)
    ):
        return

    service_data = {ATTR_ENTITY_ID: state.entity_id}

    if state.state != cur_state.state:
        if state.state == STATE_ON:
            service = WaterHeaterService.TURN_ON
        elif state.state == STATE_OFF:
            service = WaterHeaterService.TURN_OFF
        else:
            service = WaterHeaterService.SET_OPERATION_MODE
            service_data[WaterHeaterServiceArgument.OPERATION_MODE] = state.state

        await hass.services.async_call(
            DOMAIN, service, service_data, context=context, blocking=True
        )

    if (
        state.attributes.get(WaterHeaterStateAttribute.TARGET_TEMPERATURE)
        != cur_state.attributes.get(WaterHeaterStateAttribute.TARGET_TEMPERATURE)
        and state.attributes.get(WaterHeaterStateAttribute.TARGET_TEMPERATURE)
        is not None
    ):
        await hass.services.async_call(
            DOMAIN,
            WaterHeaterService.SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: state.entity_id,
                WaterHeaterServiceArgument.TEMPERATURE: state.attributes.get(
                    WaterHeaterStateAttribute.TARGET_TEMPERATURE
                ),
            },
            context=context,
            blocking=True,
        )

    if (
        state.attributes.get(WaterHeaterStateAttribute.AWAY_MODE)
        != cur_state.attributes.get(WaterHeaterStateAttribute.AWAY_MODE)
        and state.attributes.get(WaterHeaterStateAttribute.AWAY_MODE) is not None
    ):
        await hass.services.async_call(
            DOMAIN,
            WaterHeaterService.SET_AWAY_MODE,
            {
                ATTR_ENTITY_ID: state.entity_id,
                WaterHeaterServiceArgument.AWAY_MODE: state.attributes.get(
                    WaterHeaterStateAttribute.AWAY_MODE
                ),
            },
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
    """Reproduce Water heater states."""
    await asyncio.gather(
        *(
            _async_reproduce_state(
                hass, state, context=context, reproduce_options=reproduce_options
            )
            for state in states
        )
    )
