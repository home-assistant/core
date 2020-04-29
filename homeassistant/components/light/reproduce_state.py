"""Reproduce an Light state."""
import asyncio
import logging
from types import MappingProxyType
from typing import Iterable, Optional

from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import Context, State
from homeassistant.helpers.typing import HomeAssistantType

from . import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
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
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

VALID_STATES = {STATE_ON, STATE_OFF}

ATTR_GROUP = [
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_EFFECT,
    ATTR_FLASH,
    ATTR_WHITE_VALUE,
    ATTR_TRANSITION,
]

COLOR_GROUP = [
    ATTR_HS_COLOR,
    ATTR_COLOR_TEMP,
    ATTR_RGB_COLOR,
    ATTR_XY_COLOR,
    # The following color attributes are deprecated
    ATTR_PROFILE,
    ATTR_COLOR_NAME,
    ATTR_KELVIN,
]

DEPRECATED_GROUP = [
    ATTR_BRIGHTNESS_PCT,
    ATTR_COLOR_NAME,
    ATTR_FLASH,
    ATTR_KELVIN,
    ATTR_PROFILE,
    ATTR_TRANSITION,
]

DEPRECATION_WARNING = (
    "The use of other attributes than device state attributes is deprecated and will be removed in a future release. "
    "Invalid attributes are %s. Read the logs for further details: https://www.home-assistant.io/integrations/scene/"
)


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

    # Warn if deprecated attributes are used
    deprecated_attrs = [attr for attr in state.attributes if attr in DEPRECATED_GROUP]
    if deprecated_attrs:
        _LOGGER.warning(DEPRECATION_WARNING, deprecated_attrs)

    # Return if we are already at the right state.
    if cur_state.state == state.state and all(
        check_attr_equal(cur_state.attributes, state.attributes, attr)
        for attr in ATTR_GROUP + COLOR_GROUP
    ):
        return

    service_data = {ATTR_ENTITY_ID: state.entity_id}

    if state.state == STATE_ON:
        service = SERVICE_TURN_ON
        for attr in ATTR_GROUP:
            # All attributes that are not colors
            if attr in state.attributes:
                service_data[attr] = state.attributes[attr]

        for color_attr in COLOR_GROUP:
            # Choose the first color that is specified
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
