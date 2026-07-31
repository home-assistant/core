"""Reproduce a Color helper state for scenes."""

import asyncio
from collections.abc import Iterable
import logging
import re
from typing import Any

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import Context, HomeAssistant, State

from .color_math import ColorInputError, normalize, valid_xy
from .const import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_KIND,
    ATTR_SOURCE_HEX,
    ATTR_XY_COLOR,
    DOMAIN,
    FIELD_BRIGHTNESS,
    FIELD_HEX,
    FIELD_KELVIN,
    FIELD_XY,
    KIND_WHITE,
    SERVICE_CLEAR_BRIGHTNESS,
    SERVICE_SET_BRIGHTNESS,
    SERVICE_SET_COLOR,
)

_LOGGER = logging.getLogger(__name__)
_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _is_valid_xy_pair(x: Any, y: Any) -> bool:
    """Return True if the snapshot xy pair is a usable chromaticity."""
    try:
        return valid_xy(float(x), float(y))
    except TypeError, ValueError:
        return False


def _source_hex_matches(source_hex: Any, xy: Any) -> bool:
    """Return True if source_hex is a hex whose canonical xy matches the snapshot.

    Snapshots store xy rounded to 4 decimals, so an honest snapshot's
    source_hex always re-normalizes onto its own xy attribute.
    """
    if not isinstance(source_hex, str) or not _HEX_RE.match(source_hex):
        return False
    try:
        canonical = normalize({FIELD_HEX: source_hex})
    except ColorInputError:
        return False
    if not (isinstance(xy, (list, tuple)) and len(xy) == 2):
        return True
    try:
        return round(canonical.xy[0], 4) == round(float(xy[0]), 4) and round(
            canonical.xy[1], 4
        ) == round(float(xy[1]), 4)
    except TypeError, ValueError:
        return False


async def _async_reproduce_state(
    hass: HomeAssistant,
    state: State,
    *,
    context: Context | None = None,
    reproduce_options: dict[str, Any] | None = None,
) -> None:
    """Reproduce a single Color state.

    Resilient to snapshot defects: the state may be a non-hex sentinel like
    "unavailable" from a partial-load capture (the color call is skipped),
    and the brightness attribute may be missing entirely from older
    snapshots (brightness is left untouched).
    """
    if hass.states.get(state.entity_id) is None:
        _LOGGER.warning("Unable to find entity %s", state.entity_id)
        return

    attrs = state.attributes

    color_data: dict[str, Any] | None = None
    xy = attrs.get(ATTR_XY_COLOR)
    source_hex = attrs.get(ATTR_SOURCE_HEX)
    if attrs.get(ATTR_KIND) == KIND_WHITE and not attrs.get(ATTR_COLOR_TEMP_KELVIN):
        _LOGGER.debug(
            "Snapshot for %s is kind=white without kelvin; restoring as chromatic",
            state.entity_id,
        )
    if attrs.get(ATTR_KIND) == KIND_WHITE and attrs.get(ATTR_COLOR_TEMP_KELVIN):
        color_data = {FIELD_KELVIN: attrs[ATTR_COLOR_TEMP_KELVIN]}
    elif _source_hex_matches(source_hex, xy):
        # The canonical value was derived from this exact hex, so restoring
        # via hex loses nothing and preserves the source_hex attribute.
        color_data = {FIELD_HEX: source_hex}
    elif (
        isinstance(xy, (list, tuple))
        and len(xy) == 2
        and _is_valid_xy_pair(xy[0], xy[1])
    ):
        # Canonical xy beats the derived hex state (hex -> xy is lossy).
        color_data = {FIELD_XY: [float(xy[0]), float(xy[1])]}
    elif isinstance(state.state, str) and _HEX_RE.match(state.state):
        color_data = {FIELD_HEX: state.state}
    else:
        _LOGGER.debug(
            "Skipping color restore for %s: state %r not a valid representation",
            state.entity_id,
            state.state,
        )

    if color_data is not None:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_COLOR,
            {ATTR_ENTITY_ID: state.entity_id, **color_data},
            context=context,
            blocking=True,
        )

    if ATTR_BRIGHTNESS in attrs:
        snapshot_brightness = attrs[ATTR_BRIGHTNESS]
        if snapshot_brightness is None:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_CLEAR_BRIGHTNESS,
                {ATTR_ENTITY_ID: state.entity_id},
                context=context,
                blocking=True,
            )
        else:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_SET_BRIGHTNESS,
                {
                    ATTR_ENTITY_ID: state.entity_id,
                    FIELD_BRIGHTNESS: snapshot_brightness,
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
    """Reproduce Color states in parallel."""
    await asyncio.gather(
        *(
            _async_reproduce_state(
                hass, state, context=context, reproduce_options=reproduce_options
            )
            for state in states
        )
    )
