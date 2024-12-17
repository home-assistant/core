"""Reproduce an Light state."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping
import logging
from typing import Any, NamedTuple, cast

from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import Context, HomeAssistant, State
from homeassistant.util import color as color_util

from . import (
    _DEPRECATED_ATTR_COLOR_TEMP,
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_TRANSITION,
    ATTR_WHITE,
    ATTR_XY_COLOR,
)
from .const import DOMAIN, ColorMode

_LOGGER = logging.getLogger(__name__)

VALID_STATES = {STATE_ON, STATE_OFF}

ATTR_GROUP = [ATTR_BRIGHTNESS, ATTR_EFFECT]

COLOR_GROUP = [
    ATTR_HS_COLOR,
    _DEPRECATED_ATTR_COLOR_TEMP.value,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_XY_COLOR,
]


class ColorModeAttr(NamedTuple):
    """Map service data parameter to state attribute for a color mode."""

    parameter: str
    state_attr: str


COLOR_MODE_TO_ATTRIBUTE = {
    ColorMode.COLOR_TEMP: ColorModeAttr(ATTR_COLOR_TEMP_KELVIN, ATTR_COLOR_TEMP_KELVIN),
    ColorMode.HS: ColorModeAttr(ATTR_HS_COLOR, ATTR_HS_COLOR),
    ColorMode.RGB: ColorModeAttr(ATTR_RGB_COLOR, ATTR_RGB_COLOR),
    ColorMode.RGBW: ColorModeAttr(ATTR_RGBW_COLOR, ATTR_RGBW_COLOR),
    ColorMode.RGBWW: ColorModeAttr(ATTR_RGBWW_COLOR, ATTR_RGBWW_COLOR),
    ColorMode.WHITE: ColorModeAttr(ATTR_WHITE, ATTR_BRIGHTNESS),
    ColorMode.XY: ColorModeAttr(ATTR_XY_COLOR, ATTR_XY_COLOR),
}


def _color_mode_same(cur_state: State, state: State) -> bool:
    """Test if color_mode is same."""
    cur_color_mode = cur_state.attributes.get(ATTR_COLOR_MODE, ColorMode.UNKNOWN)
    saved_color_mode = state.attributes.get(ATTR_COLOR_MODE, ColorMode.UNKNOWN)

    # Guard for scenes etc. which where created before color modes were introduced
    if saved_color_mode == ColorMode.UNKNOWN:
        return True
    return cast(bool, cur_color_mode == saved_color_mode)


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
        and _color_mode_same(cur_state, state)
        and all(
            check_attr_equal(cur_state.attributes, state.attributes, attr)
            for attr in ATTR_GROUP + COLOR_GROUP
        )
    ):
        return

    service_data: dict[str, Any] = {ATTR_ENTITY_ID: state.entity_id}

    if reproduce_options is not None and ATTR_TRANSITION in reproduce_options:
        service_data[ATTR_TRANSITION] = reproduce_options[ATTR_TRANSITION]

    if state.state == STATE_ON:
        service = SERVICE_TURN_ON
        for attr in ATTR_GROUP:
            # All attributes that are not colors
            if (attr_state := state.attributes.get(attr)) is not None:
                service_data[attr] = attr_state

        if (
            state.attributes.get(ATTR_COLOR_MODE, ColorMode.UNKNOWN)
            != ColorMode.UNKNOWN
        ):
            color_mode = state.attributes[ATTR_COLOR_MODE]
            if cm_attr := COLOR_MODE_TO_ATTRIBUTE.get(color_mode):
                if (cm_attr_state := state.attributes.get(cm_attr.state_attr)) is None:
                    if (
                        color_mode != ColorMode.COLOR_TEMP
                        or (
                            mireds := state.attributes.get(
                                _DEPRECATED_ATTR_COLOR_TEMP.value
                            )
                        )
                        is None
                    ):
                        _LOGGER.warning(
                            "Color mode %s specified but attribute %s missing for: %s",
                            color_mode,
                            cm_attr.state_attr,
                            state.entity_id,
                        )
                        return
                    _LOGGER.warning(
                        "Color mode %s specified but attribute %s missing for: %s, "
                        "using color_temp (mireds) as fallback",
                        color_mode,
                        cm_attr.state_attr,
                        state.entity_id,
                    )
                    cm_attr_state = color_util.color_temperature_mired_to_kelvin(mireds)
                service_data[cm_attr.parameter] = cm_attr_state
        else:
            # Fall back to Choosing the first color that is specified
            for color_attr in COLOR_GROUP:
                if (color_attr_state := state.attributes.get(color_attr)) is not None:
                    service_data[color_attr] = color_attr_state
                    break

    elif state.state == STATE_OFF:
        service = SERVICE_TURN_OFF

    await hass.services.async_call(
        DOMAIN, service, service_data, context=context, blocking=True
    )


async def async_reproduce_states(
    hass: HomeAssistant,
    states: Iterable[State],
    *,
    context: Context | None = None,
    reproduce_options: dict[str, Any] | None = None,
) -> None:
    """Reproduce Light states."""
    await asyncio.gather(
        *(
            _async_reproduce_state(
                hass, state, context=context, reproduce_options=reproduce_options
            )
            for state in states
        )
    )


def check_attr_equal(attr1: Mapping, attr2: Mapping, attr_str: str) -> bool:
    """Return true if the given attributes are equal."""
    return attr1.get(attr_str) == attr2.get(attr_str)
