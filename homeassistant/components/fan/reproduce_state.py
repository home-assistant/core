"""Reproduce an Fan state."""

import asyncio
from collections.abc import Iterable
import logging
from typing import Any

from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import Context, HomeAssistant, State

from .const import DOMAIN, FanEntityStateAttribute, FanService, FanServiceArgument

_LOGGER = logging.getLogger(__name__)

VALID_STATES = {STATE_ON, STATE_OFF}

# Maps a state attribute to the (service, service argument) used to restore it.
# These are used as parameters to fan.turn_on service.
SPEED_AND_MODE_ATTRIBUTES = {
    FanEntityStateAttribute.PERCENTAGE: (
        FanService.SET_PERCENTAGE,
        FanServiceArgument.PERCENTAGE,
    ),
    FanEntityStateAttribute.PRESET_MODE: (
        FanService.SET_PRESET_MODE,
        FanServiceArgument.PRESET_MODE,
    ),
}

SIMPLE_ATTRIBUTES = {
    FanEntityStateAttribute.DIRECTION: (
        FanService.SET_DIRECTION,
        FanServiceArgument.DIRECTION,
    ),
    FanEntityStateAttribute.OSCILLATING: (
        FanService.OSCILLATE,
        FanServiceArgument.OSCILLATING,
    ),
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

    service_calls: dict[FanService, dict[str, Any]] = {}

    if state.state == STATE_ON:
        # The fan should be on
        if cur_state.state != STATE_ON:
            # Turn on the fan with all the speed and modes attributes.
            # The `turn_on` method will figure out in which mode to
            # turn the fan on.
            service_calls[FanService.TURN_ON] = {
                service_arg: value
                for attribute, (
                    _service,
                    service_arg,
                ) in SPEED_AND_MODE_ATTRIBUTES.items()
                if (value := state.attributes.get(attribute)) is not None
            }
        else:
            # If the fan is already on, we need to set speed or mode
            # based on the state.
            #
            # Speed and preset mode are mutually exclusive, so one of
            # them is always going to be stored as None. If we were to
            # try to set it, it will raise an error. So instead we
            # only update the one that is non-None.
            for attribute, (service, service_arg) in SPEED_AND_MODE_ATTRIBUTES.items():
                value = state.attributes.get(attribute)
                if value is not None and value != cur_state.attributes.get(attribute):
                    service_calls[service] = {service_arg: value}

        # The simple attributes are copied directly. They can only be
        # None if the fan does not support the feature in the first
        # place, so the equality check ensures we don't call the
        # services with invalid parameters.
        for attribute, (service, service_arg) in SIMPLE_ATTRIBUTES.items():
            if (value := state.attributes.get(attribute)) != cur_state.attributes.get(
                attribute
            ):
                service_calls[service] = {service_arg: value}
    elif state.state == STATE_OFF and cur_state.state != state.state:
        service_calls[FanService.TURN_OFF] = {}

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
