"""Module that groups code required to handle state restore for component."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any

from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import Context, HomeAssistant, State

from .const import (
    ATTR_AUX_HEAT,
    ATTR_FAN_MODE,
    ATTR_HUMIDITY,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_SWING_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DOMAIN,
    HVAC_MODES,
    SERVICE_SET_AUX_HEAT,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
)


async def _async_reproduce_states(
    hass: HomeAssistant,
    state: State,
    *,
    context: Context | None = None,
    reproduce_options: dict[str, Any] | None = None,
) -> None:
    """Reproduce component states."""

    async def call_service(
        service: str, keys: Iterable, data: dict[str, Any] | None = None
    ) -> None:
        """Call service with set of attributes given."""
        data = data or {}
        data["entity_id"] = state.entity_id
        for key in keys:
            if (value := state.attributes.get(key)) is not None:
                data[key] = value

        await hass.services.async_call(
            DOMAIN, service, data, blocking=True, context=context
        )

    if state.state in HVAC_MODES:
        await call_service(SERVICE_SET_HVAC_MODE, [], {ATTR_HVAC_MODE: state.state})

    if ATTR_AUX_HEAT in state.attributes:
        await call_service(SERVICE_SET_AUX_HEAT, [ATTR_AUX_HEAT])

    if (
        (ATTR_TEMPERATURE in state.attributes)
        or (ATTR_TARGET_TEMP_HIGH in state.attributes)
        or (ATTR_TARGET_TEMP_LOW in state.attributes)
    ):
        await call_service(
            SERVICE_SET_TEMPERATURE,
            [ATTR_TEMPERATURE, ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW],
        )

    if ATTR_PRESET_MODE in state.attributes:
        await call_service(SERVICE_SET_PRESET_MODE, [ATTR_PRESET_MODE])

    if ATTR_SWING_MODE in state.attributes:
        await call_service(SERVICE_SET_SWING_MODE, [ATTR_SWING_MODE])

    if ATTR_FAN_MODE in state.attributes:
        await call_service(SERVICE_SET_FAN_MODE, [ATTR_FAN_MODE])

    if ATTR_HUMIDITY in state.attributes:
        await call_service(SERVICE_SET_HUMIDITY, [ATTR_HUMIDITY])


async def async_reproduce_states(
    hass: HomeAssistant,
    states: Iterable[State],
    *,
    context: Context | None = None,
    reproduce_options: dict[str, Any] | None = None,
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
