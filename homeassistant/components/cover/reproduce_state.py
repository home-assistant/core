"""Reproduce an Cover state."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine, Iterable
from functools import partial
import logging
from typing import Any, Final

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
from homeassistant.core import Context, HomeAssistant, ServiceResponse, State
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

FULL_OPEN: Final = 100
FULL_CLOSE: Final = 0


def _determine_features(current_attrs: dict[str, Any]) -> CoverEntityFeature:
    """Determine supported features based on current attributes."""
    features = CoverEntityFeature(0)
    if ATTR_CURRENT_POSITION in current_attrs:
        features |= (
            CoverEntityFeature.SET_POSITION
            | CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
        )
    if ATTR_CURRENT_TILT_POSITION in current_attrs:
        features |= (
            CoverEntityFeature.SET_TILT_POSITION
            | CoverEntityFeature.OPEN_TILT
            | CoverEntityFeature.CLOSE_TILT
        )
    if features == CoverEntityFeature(0):
        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
    return features


async def _async_set_position(
    service_call: partial[Coroutine[Any, Any, ServiceResponse]],
    service_data: dict[str, Any],
    features: CoverEntityFeature,
    target_position: int,
) -> bool:
    """Set the position of the cover.

    Returns True if the position was set, False if there is no
    supported method for setting the position.
    """
    if target_position == FULL_CLOSE and CoverEntityFeature.CLOSE in features:
        await service_call(SERVICE_CLOSE_COVER, service_data)
    elif target_position == FULL_OPEN and CoverEntityFeature.OPEN in features:
        await service_call(SERVICE_OPEN_COVER, service_data)
    elif CoverEntityFeature.SET_POSITION in features:
        await service_call(
            SERVICE_SET_COVER_POSITION, service_data | {ATTR_POSITION: target_position}
        )
    else:
        # Requested a position but the cover doesn't support it
        return False
    return True


async def _async_set_tilt_position(
    service_call: partial[Coroutine[Any, Any, ServiceResponse]],
    service_data: dict[str, Any],
    features: CoverEntityFeature,
    target_tilt_position: int,
) -> bool:
    """Set the tilt position of the cover.

    Returns True if the tilt position was set, False if there is no
    supported method for setting the tilt position.
    """
    if target_tilt_position == FULL_CLOSE and CoverEntityFeature.CLOSE_TILT in features:
        await service_call(SERVICE_CLOSE_COVER_TILT, service_data)
    elif target_tilt_position == FULL_OPEN and CoverEntityFeature.OPEN_TILT in features:
        await service_call(SERVICE_OPEN_COVER_TILT, service_data)
    elif CoverEntityFeature.SET_TILT_POSITION in features:
        await service_call(
            SERVICE_SET_COVER_TILT_POSITION,
            service_data | {ATTR_TILT_POSITION: target_tilt_position},
        )
    else:
        # Requested a tilt position but the cover doesn't support it
        return False
    return True


async def _async_close_cover(
    service_call: partial[Coroutine[Any, Any, ServiceResponse]],
    service_data: dict[str, Any],
    features: CoverEntityFeature,
    set_position: bool,
    set_tilt: bool,
) -> None:
    """Close the cover if it was not closed by setting the position."""
    if not set_position:
        if CoverEntityFeature.CLOSE in features:
            await service_call(SERVICE_CLOSE_COVER, service_data)
        elif CoverEntityFeature.SET_POSITION in features:
            await service_call(
                SERVICE_SET_COVER_POSITION, service_data | {ATTR_POSITION: FULL_CLOSE}
            )
    if not set_tilt:
        if CoverEntityFeature.CLOSE_TILT in features:
            await service_call(SERVICE_CLOSE_COVER_TILT, service_data)
        elif CoverEntityFeature.SET_TILT_POSITION in features:
            await service_call(
                SERVICE_SET_COVER_TILT_POSITION,
                service_data | {ATTR_TILT_POSITION: FULL_CLOSE},
            )


async def _async_open_cover(
    service_call: partial[Coroutine[Any, Any, ServiceResponse]],
    service_data: dict[str, Any],
    features: CoverEntityFeature,
    set_position: bool,
    set_tilt: bool,
) -> None:
    """Open the cover if it was not opened by setting the position."""
    if not set_position:
        if CoverEntityFeature.OPEN in features:
            await service_call(SERVICE_OPEN_COVER, service_data)
        elif CoverEntityFeature.SET_POSITION in features:
            await service_call(
                SERVICE_SET_COVER_POSITION, service_data | {ATTR_POSITION: FULL_OPEN}
            )
    if not set_tilt:
        if CoverEntityFeature.OPEN_TILT in features:
            await service_call(SERVICE_OPEN_COVER_TILT, service_data)
        elif CoverEntityFeature.SET_TILT_POSITION in features:
            await service_call(
                SERVICE_SET_COVER_TILT_POSITION,
                service_data | {ATTR_TILT_POSITION: FULL_OPEN},
            )


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
    )
    if features is None:
        # Backwards compatibility for integrations that
        # don't set supported features since it previously
        # worked without it.
        _LOGGER.warning("Supported features is not set for %s", entity_id)
        features = _determine_features(current_attrs)

    service_call = partial(
        hass.services.async_call,
        DOMAIN,
        context=context,
        blocking=True,
    )
    service_data = {ATTR_ENTITY_ID: entity_id}

    set_position = (
        not position_matches
        and target_position is not None
        and await _async_set_position(
            service_call, service_data, features, target_position
        )
    )
    set_tilt = (
        not tilt_position_matches
        and target_tilt_position is not None
        and await _async_set_tilt_position(
            service_call, service_data, features, target_tilt_position
        )
    )

    if target_state in CLOSING_STATES:
        await _async_close_cover(
            service_call, service_data, features, set_position, set_tilt
        )

    elif target_state in OPENING_STATES:
        await _async_open_cover(
            service_call, service_data, features, set_position, set_tilt
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
