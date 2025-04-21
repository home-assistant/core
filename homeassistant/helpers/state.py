"""Helpers that help with state related things."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
import logging
from types import ModuleType
from typing import Any

from homeassistant.components.lock import LockState
from homeassistant.components.sun import STATE_ABOVE_HORIZON, STATE_BELOW_HORIZON
from homeassistant.const import (
    STATE_CLOSED,
    STATE_HOME,
    STATE_NOT_HOME,
    STATE_OFF,
    STATE_ON,
    STATE_OPEN,
    STATE_UNKNOWN,
)
from homeassistant.core import Context, HomeAssistant, State
from homeassistant.loader import IntegrationNotFound, async_get_integration, bind_hass

_LOGGER = logging.getLogger(__name__)


@bind_hass
async def async_reproduce_state(
    hass: HomeAssistant,
    states: State | Iterable[State],
    *,
    context: Context | None = None,
    reproduce_options: dict[str, Any] | None = None,
) -> None:
    """Reproduce a list of states on multiple domains."""
    if isinstance(states, State):
        states = [states]

    to_call: dict[str, list[State]] = defaultdict(list)

    for state in states:
        to_call[state.domain].append(state)

    async def worker(domain: str, states_by_domain: list[State]) -> None:
        try:
            integration = await async_get_integration(hass, domain)
        except IntegrationNotFound:
            _LOGGER.warning(
                "Trying to reproduce state for unknown integration: %s", domain
            )
            return

        try:
            platform: ModuleType = await integration.async_get_platform(
                "reproduce_state"
            )
        except ImportError:
            _LOGGER.warning("Integration %s does not support reproduce state", domain)
            return

        await platform.async_reproduce_states(
            hass, states_by_domain, context=context, reproduce_options=reproduce_options
        )

    if to_call:
        # run all domains in parallel
        await asyncio.gather(
            *(worker(domain, data) for domain, data in to_call.items())
        )


def state_as_number(state: State) -> float:
    """Try to coerce our state to a number.

    Raises ValueError if this is not possible.
    """
    if state.state in (
        STATE_ON,
        LockState.LOCKED,
        STATE_ABOVE_HORIZON,
        STATE_OPEN,
        STATE_HOME,
    ):
        return 1
    if state.state in (
        STATE_OFF,
        LockState.UNLOCKED,
        STATE_UNKNOWN,
        STATE_BELOW_HORIZON,
        STATE_CLOSED,
        STATE_NOT_HOME,
    ):
        return 0

    return float(state.state)


def get_device_uptime(
    current_uptime: datetime,
    last_uptime: datetime | None,
    domain: str,
    device_name: str | None = None,
) -> datetime:
    """Return device uptime, tolerate up to 'deviation_time' seconds deviation."""

    # Allow 1 minute deviation as the main purpose of this function is to
    # know if a device restarted or not.
    UPTIME_DEVIATION = 60

    if (
        not last_uptime
        or (diff := abs((current_uptime - last_uptime).total_seconds()))
        > UPTIME_DEVIATION
    ):
        if last_uptime:
            _LOGGER.debug(
                "Time deviation %s > %s for device %s [%s] with uptime %s",
                diff,
                UPTIME_DEVIATION,
                device_name or "unspecified",
                domain,
                current_uptime,
            )
        return current_uptime

    return last_uptime
