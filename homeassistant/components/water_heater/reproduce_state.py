"""Reproduce an Water heater state."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
import logging
from typing import Any

from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import Context, HomeAssistant, State

from . import (
    ATTR_OPERATION_MODE,
    ATTR_PRESET_MODE,
    DOMAIN,
    SERVICE_SET_OPERATION_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    WaterHeaterOperationMode,
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
    if (cur_state := hass.states.get(state.entity_id)) is None:
        _LOGGER.warning("Unable to find entity %s", state.entity_id)
        return

    if state.state not in WaterHeaterOperationMode.__members__.values():
        _LOGGER.warning(
            "Invalid state specified for %s: %s", state.entity_id, state.state
        )
        return

    # Return if we are already at the right state.
    if (
        cur_state.state == state.state
        and cur_state.attributes.get(ATTR_TEMPERATURE)
        == state.attributes.get(ATTR_TEMPERATURE)
        and cur_state.attributes.get(ATTR_OPERATION_MODE)
        == state.attributes.get(ATTR_OPERATION_MODE)
        and cur_state.attributes.get(ATTR_PRESET_MODE)
        == state.attributes.get(ATTR_PRESET_MODE)
    ):
        return

    service_data = {ATTR_ENTITY_ID: state.entity_id}

    if state.state != cur_state.state:
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
        state.attributes.get(ATTR_PRESET_MODE)
        != cur_state.attributes.get(ATTR_PRESET_MODE)
        and state.attributes.get(ATTR_PRESET_MODE) is not None
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {
                ATTR_ENTITY_ID: state.entity_id,
                ATTR_PRESET_MODE: state.attributes.get(ATTR_PRESET_MODE),
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
