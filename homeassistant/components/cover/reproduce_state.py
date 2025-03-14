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

    current_position = cur_state.attributes.get(ATTR_CURRENT_POSITION)
    requested_position = state.attributes.get(ATTR_CURRENT_POSITION)
    position_matches = current_position == requested_position

    requested_tilt_position = state.attributes.get(ATTR_CURRENT_TILT_POSITION)
    current_tilt_position = cur_state.attributes.get(ATTR_CURRENT_TILT_POSITION)
    tilt_position_matches = current_tilt_position == requested_tilt_position
    state_matches = cur_state.state == state.state
    # Return if we are already at the right state.
    if state_matches and position_matches and tilt_position_matches:
        return

    supported_features = try_parse_enum(
        CoverEntityFeature, cur_state.attributes.get(ATTR_SUPPORTED_FEATURES)
    ) or CoverEntityFeature(0)
    set_position: bool = False
    set_tilt: bool = False
    service_data = {ATTR_ENTITY_ID: state.entity_id}

    async def _service_call(service: str, data: dict[str, Any]) -> None:
        await hass.services.async_call(
            DOMAIN, service, data, context=context, blocking=True
        )

    if not position_matches and requested_position is not None:
        if requested_position == 0 and CoverEntityFeature.CLOSE in supported_features:
            await _service_call(SERVICE_CLOSE_COVER, service_data)
            set_position = True
        elif (
            requested_position == 100 and CoverEntityFeature.OPEN in supported_features
        ):
            await _service_call(SERVICE_OPEN_COVER, service_data)
            set_position = True
        elif CoverEntityFeature.SET_POSITION in supported_features:
            await _service_call(
                SERVICE_SET_COVER_POSITION,
                {**service_data, ATTR_POSITION: requested_position},
            )
            set_position = True

    if not tilt_position_matches and requested_tilt_position is not None:
        if (
            requested_tilt_position == 0
            and CoverEntityFeature.CLOSE_TILT in supported_features
        ):
            await _service_call(SERVICE_CLOSE_COVER_TILT, service_data)
            set_tilt = True
        elif (
            requested_tilt_position == 100
            and CoverEntityFeature.OPEN_TILT in supported_features
        ):
            await _service_call(SERVICE_OPEN_COVER_TILT, service_data)
            set_tilt = True
        elif CoverEntityFeature.SET_TILT_POSITION in supported_features:
            await _service_call(
                SERVICE_SET_COVER_TILT_POSITION,
                {**service_data, ATTR_TILT_POSITION: requested_tilt_position},
            )
            set_tilt = True

    if state_matches:
        return

    # Open/Close
    services: list[str] = []
    if state.state in {CoverState.CLOSED, CoverState.CLOSING}:
        if not set_position and CoverEntityFeature.CLOSE in supported_features:
            services.append(SERVICE_CLOSE_COVER)
        if not set_tilt and CoverEntityFeature.CLOSE_TILT in supported_features:
            services.append(SERVICE_CLOSE_COVER_TILT)
    elif state.state in {CoverState.OPEN, CoverState.OPENING}:
        if not set_position and CoverEntityFeature.OPEN in supported_features:
            services.append(SERVICE_OPEN_COVER)
        if not set_tilt and CoverEntityFeature.OPEN_TILT in supported_features:
            services.append(SERVICE_OPEN_COVER_TILT)

    for service in services:
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
