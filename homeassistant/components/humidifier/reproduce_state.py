"""Module that groups code required to handle state restore for component."""
import asyncio
import logging
from typing import Any, Dict, Iterable, Optional

from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON, STATE_OFF, STATE_ON
from homeassistant.core import Context, State
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    ATTR_HUMIDITY,
    ATTR_MODE,
    DOMAIN,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_MODE,
)

_LOGGER = logging.getLogger(__name__)


async def _async_reproduce_states(
    hass: HomeAssistantType,
    state: State,
    *,
    context: Optional[Context] = None,
    reproduce_options: Optional[Dict[str, Any]] = None,
) -> None:
    """Reproduce component states."""
    cur_state = hass.states.get(state.entity_id)

    if cur_state is None:
        _LOGGER.warning("Unable to find entity %s", state.entity_id)
        return

    async def call_service(service: str, keys: Iterable, data=None):
        """Call service with set of attributes given."""
        data = data or {}
        data["entity_id"] = state.entity_id
        for key in keys:
            if key in state.attributes:
                data[key] = state.attributes[key]

        await hass.services.async_call(
            DOMAIN, service, data, blocking=True, context=context
        )

    # First of all, turn on if needed, because the device might not
    # be able to set mode and humidity while being off
    if state.state == STATE_ON and cur_state.state != STATE_ON:
        await call_service(SERVICE_TURN_ON, [])

    # Then set the mode before target humidity, because switching modes
    # may invalidate target humidity
    cur_state = hass.states.get(state.entity_id)

    if ATTR_MODE in state.attributes and state.attributes[
        ATTR_MODE
    ] != cur_state.attributes.get(ATTR_MODE):
        await call_service(SERVICE_SET_MODE, [ATTR_MODE])

    # Next, restore target humidity for the current mode
    if ATTR_HUMIDITY in state.attributes and state.attributes[
        ATTR_HUMIDITY
    ] != cur_state.attributes.get(ATTR_HUMIDITY):
        await call_service(SERVICE_SET_HUMIDITY, [ATTR_HUMIDITY])

    # Lastly, ensure the device is off if it needs to be
    if state.state == STATE_OFF and cur_state.state != STATE_OFF:
        await call_service(SERVICE_TURN_OFF, [])

    if state.state not in {STATE_ON, STATE_OFF}:
        _LOGGER.warning(
            "Invalid state specified for %s: %s", state.entity_id, state.state
        )


async def async_reproduce_states(
    hass: HomeAssistantType,
    states: Iterable[State],
    *,
    context: Optional[Context] = None,
    reproduce_options: Optional[Dict[str, Any]] = None,
) -> None:
    """Reproduce component states."""
    await asyncio.gather(
        *(
            _async_reproduce_states(
                hass, state, context=context, reproduce_options=reproduce_options
            )
            for state in states
        )
    )
