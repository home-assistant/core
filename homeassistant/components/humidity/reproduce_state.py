"""Module that groups code required to handle state restore for component."""
import asyncio
from typing import Iterable, Optional

from homeassistant.core import Context, State
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    ATTR_PRESET_MODE,
    ATTR_HUMIDIFIER_MODE,
    ATTR_HUMIDITY,
    HUMIDIFIER_MODES,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_HUMIDIFIER_MODE,
    SERVICE_SET_HUMIDITY,
    DOMAIN,
)


async def _async_reproduce_states(
    hass: HomeAssistantType, state: State, context: Optional[Context] = None
) -> None:
    """Reproduce component states."""

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

    if state.state in HUMIDIFIER_MODES:
        await call_service(
            SERVICE_SET_HUMIDIFIER_MODE, [], {ATTR_HUMIDIFIER_MODE: state.state}
        )

    if ATTR_PRESET_MODE in state.attributes:
        await call_service(SERVICE_SET_PRESET_MODE, [ATTR_PRESET_MODE])

    if ATTR_HUMIDITY in state.attributes:
        await call_service(SERVICE_SET_HUMIDITY, [ATTR_HUMIDITY])


async def async_reproduce_states(
    hass: HomeAssistantType, states: Iterable[State], context: Optional[Context] = None
) -> None:
    """Reproduce component states."""
    await asyncio.gather(
        *(_async_reproduce_states(hass, state, context) for state in states)
    )
