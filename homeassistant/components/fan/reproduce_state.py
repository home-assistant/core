"""Reproduce an Fan state."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
import logging
from typing import Any

from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import Context, HomeAssistant, State

from . import (
    ATTR_DIRECTION,
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DOMAIN,
    SERVICE_OSCILLATE,
    SERVICE_SET_DIRECTION,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
)

_LOGGER = logging.getLogger(__name__)

VALID_STATES = {STATE_ON, STATE_OFF}

# These are used as parameters to fan.turn_on service.
SPEED_AND_MODE_ATTRIBUTES = {
    ATTR_PERCENTAGE: SERVICE_SET_PERCENTAGE,
    ATTR_PRESET_MODE: SERVICE_SET_PRESET_MODE,
}

SIMPLE_ATTRIBUTES = {  # attribute: service
    ATTR_DIRECTION: SERVICE_SET_DIRECTION,
    ATTR_OSCILLATING: SERVICE_OSCILLATE,
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

    service_calls: dict[str, dict[str, Any]] = {}

    if state.state == STATE_ON:
        # The fan should be on
        if cur_state.state != STATE_ON:
            # Turn on the fan with all the speed and modes attributes.
            # The `turn_on` method will figure out in which mode to
            # turn the fan on.
            service_calls[SERVICE_TURN_ON] = {
                attr: state.attributes.get(attr)
                for attr in SPEED_AND_MODE_ATTRIBUTES
                if state.attributes.get(attr) is not None
            }
        else:
            # If the fan is already on, we need to set speed or mode
            # based on the state.
            #
            # Speed and preset mode are mutually exclusive, so one of
            # them is always going to be stored as None. If we were to
            # try to set it, it will raise an error. So instead we
            # only update the one that is non-None.
            for attr, service in SPEED_AND_MODE_ATTRIBUTES.items():
                value = state.attributes.get(attr)
                if value is not None and value != cur_state.attributes.get(attr):
                    service_calls[service] = {attr: value}

        # The simple attributes are copied directly. They can only be
        # None if the fan does not support the feature in the first
        # place, so the equality check ensures we don't call the
        # services with invalid parameters.
        for attr, service in SIMPLE_ATTRIBUTES.items():
            if (value := state.attributes.get(attr)) != cur_state.attributes.get(attr):
                service_calls[service] = {attr: value}
    elif state.state == STATE_OFF and cur_state.state != state.state:
        service_calls[SERVICE_TURN_OFF] = {}

    for service, data in service_calls.items():
        await hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_ENTITY_ID: state.entity_id, **data},
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
    """Reproduce Fan states."""
    await asyncio.gather(
        *(
            _async_reproduce_state(
                hass, state, context=context, reproduce_options=reproduce_options
            )
            for state in states
        )
    )
