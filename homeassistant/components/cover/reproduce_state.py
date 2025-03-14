"""Reproduce an Cover state."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
import logging
from typing import Any

from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
)
from homeassistant.core import Context, HomeAssistant, State
from homeassistant.util.enum import try_parse_enum

from . import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN,
    CoverEntityFeature,
    CoverState,
)

_LOGGER = logging.getLogger(__name__)

VALID_STATES = {
    CoverState.CLOSED,
    CoverState.CLOSING,
    CoverState.OPEN,
    CoverState.OPENING,
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

    requested_position = state.attributes.get(ATTR_CURRENT_POSITION)
    position_matches = (
        cur_state.attributes.get(ATTR_CURRENT_POSITION) == requested_position
    )
    requested_tilt_position = state.attributes.get(ATTR_CURRENT_TILT_POSITION)
    tilt_position_matches = (
        cur_state.attributes.get(ATTR_CURRENT_TILT_POSITION) == requested_tilt_position
    )
    state_matches = cur_state.state == state.state
    # Return if we are already at the right state.
    if state_matches and position_matches and tilt_position_matches:
        return

    supported_features = try_parse_enum(
        CoverEntityFeature, cur_state.attributes.get(ATTR_SUPPORTED_FEATURES)
    ) or CoverEntityFeature(0)
    set_position = False
    set_tilt = False
    service_data = {ATTR_ENTITY_ID: state.entity_id}

    if (
        not position_matches
        and requested_position is not None
        and CoverEntityFeature.SET_POSITION in supported_features
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {**service_data, ATTR_POSITION: requested_position},
            context=context,
            blocking=True,
        )
        set_position = True

    if (
        not tilt_position_matches
        and requested_tilt_position is not None
        and CoverEntityFeature.SET_TILT_POSITION in supported_features
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_COVER_TILT_POSITION,
            {**service_data, ATTR_TILT_POSITION: requested_tilt_position},
            context=context,
            blocking=True,
        )
        set_tilt = True

    if (set_position and set_tilt) or state_matches:
        return

    service: str | None = None
    # Open/Close
    if state.state in {CoverState.CLOSED, CoverState.CLOSING}:
        if CoverEntityFeature.CLOSE in supported_features:
            service = SERVICE_CLOSE_COVER
        elif CoverEntityFeature.CLOSE_TILT in supported_features:
            service = SERVICE_CLOSE_COVER_TILT
        # Fallback for features not being set for backwards compatibility
        elif ATTR_CURRENT_POSITION in state.attributes:
            service = SERVICE_CLOSE_COVER
        elif ATTR_CURRENT_TILT_POSITION in state.attributes:
            service = SERVICE_CLOSE_COVER_TILT
    elif state.state in {CoverState.OPEN, CoverState.OPENING}:
        if CoverEntityFeature.OPEN in supported_features:
            service = SERVICE_OPEN_COVER
        elif CoverEntityFeature.OPEN_TILT in supported_features:
            service = SERVICE_OPEN_COVER_TILT
        # Fallback for features not being set for backwards compatibility
        elif ATTR_CURRENT_POSITION in state.attributes:
            service = SERVICE_OPEN_COVER
        elif ATTR_CURRENT_TILT_POSITION in state.attributes:
            service = SERVICE_OPEN_COVER_TILT

    if service:
        await hass.services.async_call(
            DOMAIN,
            service,
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
