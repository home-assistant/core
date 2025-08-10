"""Reproduce an Alarm control panel state."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
import logging
from typing import Any, Final

from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_CUSTOM_BYPASS,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_ARM_VACATION,
    SERVICE_ALARM_DISARM,
    SERVICE_ALARM_TRIGGER,
)
from homeassistant.core import Context, HomeAssistant, State

from . import DOMAIN, AlarmControlPanelState

_LOGGER: Final = logging.getLogger(__name__)

VALID_STATES: Final[set[str]] = {
    AlarmControlPanelState.ARMED_AWAY,
    AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
    AlarmControlPanelState.ARMED_HOME,
    AlarmControlPanelState.ARMED_NIGHT,
    AlarmControlPanelState.ARMED_VACATION,
    AlarmControlPanelState.DISARMED,
    AlarmControlPanelState.TRIGGERED,
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

    # Return if we are already at the right state.
    if cur_state.state == state.state:
        return

    service_data = {ATTR_ENTITY_ID: state.entity_id}

    if state.state == AlarmControlPanelState.ARMED_AWAY:
        service = SERVICE_ALARM_ARM_AWAY
    elif state.state == AlarmControlPanelState.ARMED_CUSTOM_BYPASS:
        service = SERVICE_ALARM_ARM_CUSTOM_BYPASS
    elif state.state == AlarmControlPanelState.ARMED_HOME:
        service = SERVICE_ALARM_ARM_HOME
    elif state.state == AlarmControlPanelState.ARMED_NIGHT:
        service = SERVICE_ALARM_ARM_NIGHT
    elif state.state == AlarmControlPanelState.ARMED_VACATION:
        service = SERVICE_ALARM_ARM_VACATION
    elif state.state == AlarmControlPanelState.DISARMED:
        service = SERVICE_ALARM_DISARM
    elif state.state == AlarmControlPanelState.TRIGGERED:
        service = SERVICE_ALARM_TRIGGER

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
    """Reproduce Alarm control panel states."""
    await asyncio.gather(
        *(
            _async_reproduce_state(
                hass, state, context=context, reproduce_options=reproduce_options
            )
            for state in states
        )
    )
