"""Reproduce an Light state."""
import asyncio
import logging
from types import MappingProxyType
from typing import Iterable, Optional

from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_ON,
    STATE_OFF,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import Context, State
from homeassistant.helpers.typing import HomeAssistantType

from . import (
    DOMAIN,
    ATTR_BRIGHTNESS,
    ATTR_COLOR_NAME,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_FLASH,
    ATTR_HS_COLOR,
    ATTR_KELVIN,
    ATTR_PROFILE,
    ATTR_RGB_COLOR,
    ATTR_TRANSITION,
    ATTR_WHITE_VALUE,
    ATTR_XY_COLOR,
)

_LOGGER = logging.getLogger(__name__)

VALID_STATES = {STATE_ON, STATE_OFF}
COLOR_GROUP = [
    ATTR_COLOR_NAME,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_KELVIN,
    ATTR_PROFILE,
    ATTR_RGB_COLOR,
    ATTR_XY_COLOR,
]


async def _async_reproduce_state(
    hass: HomeAssistantType, state: State, context: Optional[Context] = None
) -> None:
    """Reproduce a single state."""
    cur_state = hass.states.get(state.entity_id)

    if cur_state is None:
        _LOGGER.warning("Unable to find entity %s", state.entity_id)
        return

    if state.state not in VALID_STATES:
        _LOGGER.warning(
            "Invalid state specified for %s: %s", state.entity_id, state.state
        )
        return

    # Return if we are already at the right state.
    # pylint: disable=too-many-boolean-expressions
    if (
        cur_state.state == state.state
        and check_attr_equal(cur_state.attributes, state.attributes, ATTR_BRIGHTNESS)
        and check_attr_equal(cur_state.attributes, state.attributes, ATTR_COLOR_NAME)
        and check_attr_equal(cur_state.attributes, state.attributes, ATTR_COLOR_TEMP)
        and check_attr_equal(cur_state.attributes, state.attributes, ATTR_EFFECT)
        and check_attr_equal(cur_state.attributes, state.attributes, ATTR_FLASH)
        and check_attr_equal(cur_state.attributes, state.attributes, ATTR_HS_COLOR)
        and check_attr_equal(cur_state.attributes, state.attributes, ATTR_KELVIN)
        and check_attr_equal(cur_state.attributes, state.attributes, ATTR_PROFILE)
        and check_attr_equal(cur_state.attributes, state.attributes, ATTR_RGB_COLOR)
        and check_attr_equal(cur_state.attributes, state.attributes, ATTR_TRANSITION)
        and check_attr_equal(cur_state.attributes, state.attributes, ATTR_WHITE_VALUE)
        and check_attr_equal(cur_state.attributes, state.attributes, ATTR_XY_COLOR)
    ):
        return

    service_data = {ATTR_ENTITY_ID: state.entity_id}

    if state.state == STATE_ON:
        service = SERVICE_TURN_ON
        if ATTR_BRIGHTNESS in state.attributes:
            service_data[ATTR_BRIGHTNESS] = state.attributes[ATTR_BRIGHTNESS]
        if ATTR_EFFECT in state.attributes:
            service_data[ATTR_EFFECT] = state.attributes[ATTR_EFFECT]
        if ATTR_FLASH in state.attributes:
            service_data[ATTR_FLASH] = state.attributes[ATTR_FLASH]
        if ATTR_TRANSITION in state.attributes:
            service_data[ATTR_TRANSITION] = state.attributes[ATTR_TRANSITION]
        if ATTR_WHITE_VALUE in state.attributes:
            service_data[ATTR_WHITE_VALUE] = state.attributes[ATTR_WHITE_VALUE]

        for color_attr in COLOR_GROUP:
            if color_attr in state.attributes:
                service_data[color_attr] = state.attributes[color_attr]
                break

    elif state.state == STATE_OFF:
        service = SERVICE_TURN_OFF

    await hass.services.async_call(
        DOMAIN, service, service_data, context=context, blocking=True
    )


async def async_reproduce_states(
    hass: HomeAssistantType, states: Iterable[State], context: Optional[Context] = None
) -> None:
    """Reproduce Light states."""
    await asyncio.gather(
        *(_async_reproduce_state(hass, state, context) for state in states)
    )


def check_attr_equal(
    attr1: MappingProxyType, attr2: MappingProxyType, attr_str: str
) -> bool:
    """Return true if the given attributes are equal."""
    return attr1.get(attr_str) == attr2.get(attr_str)
