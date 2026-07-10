"""Module that groups code required to handle state restore for component."""

import asyncio
from collections.abc import Iterable
from typing import Any

from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import Context, HomeAssistant, State

from .const import (
    ATTR_FAN_MODE,
    ATTR_HUMIDITY,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_SWING_HORIZONTAL_MODE,
    ATTR_SWING_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DOMAIN,
    HVAC_MODES,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_HORIZONTAL_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    ClimateEntityStateAttribute,
)

# Maps a state attribute to the service call argument used to restore it.
_STATE_ATTRIBUTE_TO_SERVICE_ARG: dict[ClimateEntityStateAttribute, str] = {
    ClimateEntityStateAttribute.TARGET_TEMPERATURE: ATTR_TEMPERATURE,
    ClimateEntityStateAttribute.TARGET_TEMP_HIGH: ATTR_TARGET_TEMP_HIGH,
    ClimateEntityStateAttribute.TARGET_TEMP_LOW: ATTR_TARGET_TEMP_LOW,
    ClimateEntityStateAttribute.PRESET_MODE: ATTR_PRESET_MODE,
    ClimateEntityStateAttribute.SWING_MODE: ATTR_SWING_MODE,
    ClimateEntityStateAttribute.SWING_HORIZONTAL_MODE: ATTR_SWING_HORIZONTAL_MODE,
    ClimateEntityStateAttribute.FAN_MODE: ATTR_FAN_MODE,
    ClimateEntityStateAttribute.TARGET_HUMIDITY: ATTR_HUMIDITY,
}


async def _async_reproduce_states(
    hass: HomeAssistant,
    state: State,
    *,
    context: Context | None = None,
    reproduce_options: dict[str, Any] | None = None,
) -> None:
    """Reproduce component states."""

    async def call_service(
        service: str,
        attributes: Iterable[ClimateEntityStateAttribute],
        data: dict[str, Any] | None = None,
    ) -> None:
        """Call service with the given state attributes."""
        data = data or {}
        data["entity_id"] = state.entity_id
        for attribute in attributes:
            if (value := state.attributes.get(attribute)) is not None:
                data[_STATE_ATTRIBUTE_TO_SERVICE_ARG[attribute]] = value

        await hass.services.async_call(
            DOMAIN, service, data, blocking=True, context=context
        )

    if state.state in HVAC_MODES:
        await call_service(SERVICE_SET_HVAC_MODE, [], {ATTR_HVAC_MODE: state.state})

    if (
        state.attributes.get(ClimateEntityStateAttribute.TARGET_TEMPERATURE) is not None
        or state.attributes.get(ClimateEntityStateAttribute.TARGET_TEMP_HIGH)
        is not None
        or state.attributes.get(ClimateEntityStateAttribute.TARGET_TEMP_LOW) is not None
    ):
        await call_service(
            SERVICE_SET_TEMPERATURE,
            [
                ClimateEntityStateAttribute.TARGET_TEMPERATURE,
                ClimateEntityStateAttribute.TARGET_TEMP_HIGH,
                ClimateEntityStateAttribute.TARGET_TEMP_LOW,
            ],
        )

    if (
        ClimateEntityStateAttribute.PRESET_MODE in state.attributes
        and state.attributes[ClimateEntityStateAttribute.PRESET_MODE] is not None
    ):
        await call_service(
            SERVICE_SET_PRESET_MODE, [ClimateEntityStateAttribute.PRESET_MODE]
        )

    if (
        ClimateEntityStateAttribute.SWING_MODE in state.attributes
        and state.attributes[ClimateEntityStateAttribute.SWING_MODE] is not None
    ):
        await call_service(
            SERVICE_SET_SWING_MODE, [ClimateEntityStateAttribute.SWING_MODE]
        )

    if (
        ClimateEntityStateAttribute.SWING_HORIZONTAL_MODE in state.attributes
        and state.attributes[ClimateEntityStateAttribute.SWING_HORIZONTAL_MODE]
        is not None
    ):
        await call_service(
            SERVICE_SET_SWING_HORIZONTAL_MODE,
            [ClimateEntityStateAttribute.SWING_HORIZONTAL_MODE],
        )

    if (
        ClimateEntityStateAttribute.FAN_MODE in state.attributes
        and state.attributes[ClimateEntityStateAttribute.FAN_MODE] is not None
    ):
        await call_service(SERVICE_SET_FAN_MODE, [ClimateEntityStateAttribute.FAN_MODE])

    if ClimateEntityStateAttribute.TARGET_HUMIDITY in state.attributes:
        await call_service(
            SERVICE_SET_HUMIDITY, [ClimateEntityStateAttribute.TARGET_HUMIDITY]
        )


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
