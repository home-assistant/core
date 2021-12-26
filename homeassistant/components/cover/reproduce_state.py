"""Reproduce an Cover state."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
import logging
from typing import Any

from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.core import Context, HomeAssistant, State

from . import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

VALID_STATES = {STATE_CLOSED, STATE_CLOSING, STATE_OPEN, STATE_OPENING}


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
        and cur_state.attributes.get(ATTR_CURRENT_POSITION)
        == state.attributes.get(ATTR_CURRENT_POSITION)
        and cur_state.attributes.get(ATTR_CURRENT_TILT_POSITION)
        == state.attributes.get(ATTR_CURRENT_TILT_POSITION)
    ):
        return

    service_data = {ATTR_ENTITY_ID: state.entity_id}
    service_data_tilting = {ATTR_ENTITY_ID: state.entity_id}

    if not (
        cur_state.state == state.state
        and cur_state.attributes.get(ATTR_CURRENT_POSITION)
        == state.attributes.get(ATTR_CURRENT_POSITION)
    ):
        # Open/Close
        if state.state in [STATE_CLOSED, STATE_CLOSING]:
            service = SERVICE_CLOSE_COVER
        elif state.state in [STATE_OPEN, STATE_OPENING]:
            if (
                ATTR_CURRENT_POSITION in cur_state.attributes
                and ATTR_CURRENT_POSITION in state.attributes
            ):
                service = SERVICE_SET_COVER_POSITION
                service_data[ATTR_POSITION] = state.attributes[ATTR_CURRENT_POSITION]
            else:
                service = SERVICE_OPEN_COVER

        await hass.services.async_call(
            DOMAIN, service, service_data, context=context, blocking=True
        )

    if (
        ATTR_CURRENT_TILT_POSITION in state.attributes
        and ATTR_CURRENT_TILT_POSITION in cur_state.attributes
        and cur_state.attributes.get(ATTR_CURRENT_TILT_POSITION)
        != state.attributes.get(ATTR_CURRENT_TILT_POSITION)
    ):
        # Tilt position
        if state.attributes.get(ATTR_CURRENT_TILT_POSITION) == 100:
            service_tilting = SERVICE_OPEN_COVER_TILT
        elif state.attributes.get(ATTR_CURRENT_TILT_POSITION) == 0:
            service_tilting = SERVICE_CLOSE_COVER_TILT
        else:
            service_tilting = SERVICE_SET_COVER_TILT_POSITION
            service_data_tilting[ATTR_TILT_POSITION] = state.attributes[
                ATTR_CURRENT_TILT_POSITION
            ]

        await hass.services.async_call(
            DOMAIN,
            service_tilting,
            service_data_tilting,
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
    """Reproduce Cover states."""
    # Reproduce states in parallel.
    await asyncio.gather(
        *(
            _async_reproduce_state(
                hass, state, context=context, reproduce_options=reproduce_options
            )
            for state in states
        )
    )
