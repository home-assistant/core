"""Reproduce an Input Color state."""

import asyncio
from collections.abc import Iterable
import logging
from typing import Any

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import Context, HomeAssistant, State

from . import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HEX_COLOR,
    DOMAIN,
    SERVICE_CLEAR_BRIGHTNESS,
    SERVICE_SET_BRIGHTNESS,
    SERVICE_SET_COLOR,
)
from .color_math import FIELD_HEX, FIELD_KELVIN

_LOGGER = logging.getLogger(__name__)


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

    if cur_state.state == state.state and cur_state.attributes.get(
        ATTR_BRIGHTNESS
    ) == state.attributes.get(ATTR_BRIGHTNESS):
        return

    service_data: dict[str, Any]
    if (kelvin := state.attributes.get(ATTR_COLOR_TEMP_KELVIN)) is not None:
        service_data = {ATTR_ENTITY_ID: state.entity_id, FIELD_KELVIN: kelvin}
    else:
        service_data = {
            ATTR_ENTITY_ID: state.entity_id,
            FIELD_HEX: state.attributes.get(ATTR_HEX_COLOR, state.state),
        }

    if (brightness := state.attributes.get(ATTR_BRIGHTNESS)) is not None:
        service_data[ATTR_BRIGHTNESS] = brightness

    await hass.services.async_call(
        DOMAIN, SERVICE_SET_COLOR, service_data, context=context, blocking=True
    )

    if (
        ATTR_BRIGHTNESS in state.attributes
        and state.attributes[ATTR_BRIGHTNESS] is None
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CLEAR_BRIGHTNESS,
            {ATTR_ENTITY_ID: state.entity_id},
            context=context,
            blocking=True,
        )
    elif ATTR_BRIGHTNESS in state.attributes:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_BRIGHTNESS,
            {
                ATTR_ENTITY_ID: state.entity_id,
                ATTR_BRIGHTNESS: state.attributes[ATTR_BRIGHTNESS],
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
    """Reproduce Input Color states."""
    await asyncio.gather(
        *(
            _async_reproduce_state(
                hass, state, context=context, reproduce_options=reproduce_options
            )
            for state in states
        )
    )
