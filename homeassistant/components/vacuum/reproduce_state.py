"""Reproduce an Vacuum state."""

import asyncio
from collections.abc import Iterable
import logging
from typing import Any

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import Context, HomeAssistant, State

from . import DOMAIN, VacuumActivity
from .const import VacuumEntityStateAttribute, VacuumService

_LOGGER = logging.getLogger(__name__)

VALID_STATES_STATE = {
    VacuumActivity.CLEANING,
    VacuumActivity.DOCKED,
    VacuumActivity.IDLE,
    VacuumActivity.PAUSED,
    VacuumActivity.RETURNING,
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

    if state.state not in VALID_STATES_STATE:
        _LOGGER.warning(
            "Invalid state specified for %s: %s", state.entity_id, state.state
        )
        return

    # Return if we are already at the right state.
    if cur_state.state == state.state and cur_state.attributes.get(
        VacuumEntityStateAttribute.FAN_SPEED
    ) == state.attributes.get(VacuumEntityStateAttribute.FAN_SPEED):
        return

    service_data = {ATTR_ENTITY_ID: state.entity_id}

    if cur_state.state != state.state:
        # Wrong state
        if state.state == VacuumActivity.CLEANING:
            service = VacuumService.START
        elif state.state in [VacuumActivity.DOCKED, VacuumActivity.RETURNING]:
            service = VacuumService.RETURN_TO_BASE
        elif state.state == VacuumActivity.IDLE:
            service = VacuumService.STOP
        elif state.state == VacuumActivity.PAUSED:
            service = VacuumService.PAUSE

        await hass.services.async_call(
            DOMAIN, service, service_data, context=context, blocking=True
        )

    if cur_state.attributes.get(
        VacuumEntityStateAttribute.FAN_SPEED
    ) != state.attributes.get(VacuumEntityStateAttribute.FAN_SPEED):
        # Wrong fan speed
        service_data["fan_speed"] = state.attributes[
            VacuumEntityStateAttribute.FAN_SPEED
        ]
        await hass.services.async_call(
            DOMAIN,
            VacuumService.SET_FAN_SPEED,
            service_data,
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
