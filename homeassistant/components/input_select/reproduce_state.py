"""Reproduce an Input select state."""

import asyncio
from collections.abc import Iterable
import logging
from typing import Any

from homeassistant.components.select import SelectEntityCapabilityAttribute
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import Context, HomeAssistant, State

from .const import DOMAIN, InputSelectService, InputSelectServiceArgument

_LOGGER = logging.getLogger(__name__)


async def _async_reproduce_state(
    hass: HomeAssistant,
    state: State,
    *,
    context: Context | None = None,
    reproduce_options: dict[str, Any] | None = None,
) -> None:
    """Reproduce a single state."""
    # Return if we can't find entity
    if (cur_state := hass.states.get(state.entity_id)) is None:
        _LOGGER.warning("Unable to find entity %s", state.entity_id)
        return

    # Return if we are already at the right state.
    if cur_state.state == state.state and cur_state.attributes.get(
        SelectEntityCapabilityAttribute.OPTIONS
    ) == state.attributes.get(SelectEntityCapabilityAttribute.OPTIONS):
        return

    # Set service data
    service_data = {ATTR_ENTITY_ID: state.entity_id}

    # If options are specified, call set_options
    if SelectEntityCapabilityAttribute.OPTIONS in state.attributes:
        service = InputSelectService.SET_OPTIONS
        service_data[InputSelectServiceArgument.OPTIONS] = state.attributes[
            SelectEntityCapabilityAttribute.OPTIONS
        ]

        await hass.services.async_call(
            DOMAIN, service, service_data, context=context, blocking=True
        )

        # Remove options from service_data so we can
        # reuse service_data in next call
        del service_data[InputSelectServiceArgument.OPTIONS]

    # Call select_option
    service = InputSelectService.SELECT_OPTION
    service_data[InputSelectServiceArgument.OPTION] = state.state

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
    """Reproduce Input select states."""
    # Reproduce states in parallel.
    await asyncio.gather(
        *(
            _async_reproduce_state(
                hass, state, context=context, reproduce_options=reproduce_options
            )
            for state in states
        )
    )
