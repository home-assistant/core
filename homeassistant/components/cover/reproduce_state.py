"""Reproduce an Cover state."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from functools import partial
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


OPENING_STATES = {CoverState.OPENING, CoverState.OPEN}
CLOSING_STATES = {CoverState.CLOSING, CoverState.CLOSED}
VALID_STATES: set[CoverState] = OPENING_STATES | CLOSING_STATES


async def _async_reproduce_state(
    hass: HomeAssistant,
    state: State,
    *,
    context: Context | None = None,
    reproduce_options: dict[str, Any] | None = None,
) -> None:
    """Reproduce a single state."""
    entity_id = state.entity_id
    if (cur_state := hass.states.get(entity_id)) is None:
        _LOGGER.warning("Unable to find entity %s", entity_id)
        return

    if (target_state := state.state) not in VALID_STATES:
        _LOGGER.warning("Invalid state specified for %s: %s", entity_id, target_state)
        return

    current_attrs = cur_state.attributes
    target_attrs = state.attributes

    current_position = current_attrs.get(ATTR_CURRENT_POSITION)
    target_position = target_attrs.get(ATTR_CURRENT_POSITION)
    position_matches = current_position == target_position

    current_tilt_position = current_attrs.get(ATTR_CURRENT_TILT_POSITION)
    target_tilt_position = target_attrs.get(ATTR_CURRENT_TILT_POSITION)
    tilt_position_matches = current_tilt_position == target_tilt_position

    state_matches = cur_state.state == target_state
    # Return if we are already at the right state.
    if state_matches and position_matches and tilt_position_matches:
        return

    features = try_parse_enum(
        CoverEntityFeature, current_attrs.get(ATTR_SUPPORTED_FEATURES)
    ) or CoverEntityFeature(0)
    set_position = not position_matches and target_position is not None
    service_data = {ATTR_ENTITY_ID: entity_id}

    _service_call = partial(
        hass.services.async_call,
        DOMAIN,
        context=context,
        blocking=True,
    )
    if set_position := not position_matches and target_position is not None:
        if target_position == 0 and CoverEntityFeature.CLOSE in features:
            await _service_call(SERVICE_CLOSE_COVER, service_data)
        elif target_position == 100 and CoverEntityFeature.OPEN in features:
            await _service_call(SERVICE_OPEN_COVER, service_data)
        elif CoverEntityFeature.SET_POSITION in features:
            await _service_call(
                SERVICE_SET_COVER_POSITION,
                service_data | {ATTR_POSITION: target_position},
            )
        else:
            # Requested a position but the cover doesn't support it
            set_position = False

    if set_tilt := not tilt_position_matches and target_tilt_position is not None:
        if target_tilt_position == 0 and CoverEntityFeature.CLOSE_TILT in features:
            await _service_call(SERVICE_CLOSE_COVER_TILT, service_data)
        elif target_tilt_position == 100 and CoverEntityFeature.OPEN_TILT in features:
            await _service_call(SERVICE_OPEN_COVER_TILT, service_data)
        elif CoverEntityFeature.SET_TILT_POSITION in features:
            await _service_call(
                SERVICE_SET_COVER_TILT_POSITION,
                service_data | {ATTR_TILT_POSITION: target_tilt_position},
            )
        else:
            # Requested a tilt position but the cover doesn't support it
            set_tilt = False

    # Open/Close
    if target_state in CLOSING_STATES:
        if not set_position and CoverEntityFeature.CLOSE in features:
            await _service_call(SERVICE_CLOSE_COVER, service_data)
        if not set_tilt and CoverEntityFeature.CLOSE_TILT in features:
            await _service_call(SERVICE_CLOSE_COVER_TILT, service_data)
    elif target_state in OPENING_STATES:
        if not set_position and CoverEntityFeature.OPEN in features:
            await _service_call(SERVICE_OPEN_COVER, service_data)
        if not set_tilt and CoverEntityFeature.OPEN_TILT in features:
            await _service_call(SERVICE_OPEN_COVER_TILT, service_data)


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
