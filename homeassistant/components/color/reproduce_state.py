"""Reproduce a Color helper state for scenes."""

import asyncio
from collections.abc import Iterable
import logging
from typing import Any

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import Context, HomeAssistant, State
from homeassistant.exceptions import ServiceValidationError

from .color_math import ColorInputError, derive_hex, normalize, valid_hex, valid_xy
from .const import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HEX_COLOR,
    ATTR_HS_COLOR,
    ATTR_KIND,
    ATTR_SOURCE,
    ATTR_XY_COLOR,
    DOMAIN,
    FIELD_BRIGHTNESS,
    FIELD_HEX,
    FIELD_HS,
    FIELD_KELVIN,
    FIELD_XY,
    KIND_WHITE,
    MAX_KELVIN,
    MIN_KELVIN,
    SERVICE_CLEAR_BRIGHTNESS,
    SERVICE_SET_BRIGHTNESS,
    SERVICE_SET_COLOR,
)

_LOGGER = logging.getLogger(__name__)


def _valid_kelvin(value: Any) -> bool:
    """Return True if the snapshot kelvin passes the set_color schema."""
    try:
        return MIN_KELVIN <= int(value) <= MAX_KELVIN
    except TypeError, ValueError, OverflowError:
        return False


def _valid_brightness(value: Any) -> bool:
    """Return True if the snapshot brightness passes the service schema."""
    try:
        return 0 <= int(value) <= 255
    except TypeError, ValueError, OverflowError:
        return False


def _is_valid_xy_pair(x: Any, y: Any) -> bool:
    """Return True if the snapshot xy pair is a usable chromaticity."""
    try:
        return valid_xy(float(x), float(y))
    except TypeError, ValueError, OverflowError:
        return False


def _snapshot_source_shape(
    attrs: dict[str, Any], snapshot_hex: Any
) -> dict[str, Any] | None:
    """Return the snapshot's explicit `source` shape if it is trustworthy.

    Snapshot data is untrusted: the shape must normalize cleanly, and when
    the snapshot carries a hex state it must re-derive that hex — a mismatch
    means an edited or partially captured snapshot, so fall back to inference.
    """
    source = attrs.get(ATTR_SOURCE)
    if not isinstance(source, dict) or len(source) != 1:
        return None
    ((field, value),) = source.items()
    if not isinstance(field, str):
        return None
    try:
        canonical = normalize({field: value})
    except ColorInputError:
        return None
    if valid_hex(snapshot_hex) and derive_hex(canonical) != str(snapshot_hex).upper():
        return None
    return {field: value}


def _snapshot_source_pair(
    field: str, value: Any, snapshot_hex: Any
) -> list[float] | None:
    """Return the pair to restore if `field: value` re-derives the snapshot's hex.

    Snapshots do not record which shape the user set, but the source shape's
    echo always re-derives the snapshot's hex state, while a rounded derived
    view generally does not — so this identifies the exact source to restore.
    """
    if not valid_hex(snapshot_hex) or not isinstance(value, (list, tuple)):
        return None
    try:
        canonical = normalize({field: list(value)})
    except ColorInputError:
        return None
    if derive_hex(canonical) != str(snapshot_hex).upper():
        return None
    return [float(value[0]), float(value[1])]


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
    hs = attrs.get(ATTR_HS_COLOR)
    # The state string is the hex echo; older/minimal snapshots may only
    # carry the attribute.
    snapshot_hex = state.state if valid_hex(state.state) else attrs.get(ATTR_HEX_COLOR)
    if attrs.get(ATTR_KIND) == KIND_WHITE and not attrs.get(ATTR_COLOR_TEMP_KELVIN):
        _LOGGER.debug(
            "Snapshot for %s is kind=white without kelvin; restoring as chromatic",
            state.entity_id,
        )
    if (source_shape := _snapshot_source_shape(attrs, snapshot_hex)) is not None:
        # Newer snapshots record the user's exact input shape; restore it
        # directly instead of inferring the shape from the derived views.
        color_data = source_shape
    elif (
        attrs.get(ATTR_KIND) == KIND_WHITE
        and attrs.get(ATTR_COLOR_TEMP_KELVIN)
        and _valid_kelvin(attrs[ATTR_COLOR_TEMP_KELVIN])
    ):
        color_data = {FIELD_KELVIN: int(attrs[ATTR_COLOR_TEMP_KELVIN])}
    elif (xy_pair := _snapshot_source_pair(FIELD_XY, xy, snapshot_hex)) is not None:
        # The snapshot's hex derives from this exact xy, so xy was the
        # user's shape (or an equivalent one); restore it unchanged.
        color_data = {FIELD_XY: xy_pair}
    elif (hs_pair := _snapshot_source_pair(FIELD_HS, hs, snapshot_hex)) is not None:
        color_data = {FIELD_HS: hs_pair}
    elif valid_hex(snapshot_hex):
        # sRGB shapes (hex/rgb/color_name) all re-derive exactly from the
        # hex echo, so nothing is lost restoring them via hex.
        color_data = {FIELD_HEX: str(snapshot_hex)}
    elif (
        isinstance(xy, (list, tuple))
        and len(xy) == 2
        and _is_valid_xy_pair(xy[0], xy[1])
    ):
        # Hex-less snapshot: the canonical xy is the best remaining data.
        color_data = {FIELD_XY: [float(xy[0]), float(xy[1])]}
    else:
        _LOGGER.debug(
            "Skipping color restore for %s: state %r not a valid representation",
            state.entity_id,
            state.state,
        )

    if color_data is not None:
        # Snapshot data is untrusted; a value the guards above let through
        # (e.g. a #000000 state string) must not abort the whole scene.
        try:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_SET_COLOR,
                {ATTR_ENTITY_ID: state.entity_id, **color_data},
                context=context,
                blocking=True,
            )
        except vol.Invalid, ServiceValidationError:
            _LOGGER.warning(
                "Unable to restore color %s for %s", color_data, state.entity_id
            )

    if ATTR_BRIGHTNESS in attrs:
        snapshot_brightness = attrs[ATTR_BRIGHTNESS]
        if snapshot_brightness is not None and not _valid_brightness(
            snapshot_brightness
        ):
            _LOGGER.debug(
                "Skipping brightness restore for %s: %r is not a valid brightness",
                state.entity_id,
                snapshot_brightness,
            )
        elif snapshot_brightness is None:
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
