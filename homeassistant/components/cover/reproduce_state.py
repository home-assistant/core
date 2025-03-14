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
    # Return if we are already at the right state.
    if cur_state.state == state.state and position_matches and tilt_position_matches:
        return

    service: str | None = None
    if cur_state.state != state.state:
        service_data = {ATTR_ENTITY_ID: state.entity_id}
        supported_features = try_parse_enum(
            CoverEntityFeature, cur_state.attributes.get(ATTR_SUPPORTED_FEATURES)
        ) or CoverEntityFeature(0)
        if (
            not position_matches
            and requested_position is not None
            and CoverEntityFeature.SET_POSITION in supported_features
        ):
            service = SERVICE_SET_COVER_POSITION
            service_data[ATTR_POSITION] = state.attributes[ATTR_CURRENT_POSITION]
        # Open/Close
        elif state.state in {CoverState.CLOSED, CoverState.CLOSING}:
            if CoverEntityFeature.CLOSE in supported_features:
                service = SERVICE_CLOSE_COVER
            elif (
                CoverEntityFeature.CLOSE_TILT in supported_features
                and ATTR_CURRENT_TILT_POSITION not in state.attributes
            ):
                service = SERVICE_CLOSE_COVER_TILT
        elif state.state in {CoverState.OPEN, CoverState.OPENING}:
            if CoverEntityFeature.OPEN in supported_features:
                service = SERVICE_OPEN_COVER
            elif (
                CoverEntityFeature.OPEN_TILT in supported_features
                and ATTR_CURRENT_TILT_POSITION not in state.attributes
            ):
                service = SERVICE_OPEN_COVER_TILT

        if service:
            await hass.services.async_call(
                DOMAIN, service, service_data, context=context, blocking=True
            )

    service_data_tilting = {ATTR_ENTITY_ID: state.entity_id}

    if (
        ATTR_CURRENT_TILT_POSITION in state.attributes
        and ATTR_CURRENT_TILT_POSITION in cur_state.attributes
        and not tilt_position_matches
        and service not in {SERVICE_OPEN_COVER_TILT, SERVICE_CLOSE_COVER_TILT}
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
