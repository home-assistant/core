"""Reproduce an input boolean state."""
import asyncio
import logging
from typing import Any, Dict, Iterable, Optional

from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import Context, State
from homeassistant.helpers.typing import HomeAssistantType

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def _async_reproduce_states(
    hass: HomeAssistantType,
    state: State,
    *,
    context: Optional[Context] = None,
    reproduce_options: Optional[Dict[str, Any]] = None,
) -> None:
    """Reproduce input boolean states."""
    cur_state = hass.states.get(state.entity_id)

    if cur_state is None:
        _LOGGER.warning("Unable to find entity %s", state.entity_id)
        return

    if state.state not in (STATE_ON, STATE_OFF):
        _LOGGER.warning(
            "Invalid state specified for %s: %s", state.entity_id, state.state
        )
        return

    if cur_state.state == state.state:
        return

    service = SERVICE_TURN_ON if state.state == STATE_ON else SERVICE_TURN_OFF

    await hass.services.async_call(
        DOMAIN,
        service,
        {ATTR_ENTITY_ID: state.entity_id},
        context=context,
        blocking=True,
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
