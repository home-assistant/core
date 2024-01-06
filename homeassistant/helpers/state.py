"""Helpers that help with state related things."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Iterable
import logging
from types import ModuleType
from typing import Any

from homeassistant.components.sun import STATE_ABOVE_HORIZON, STATE_BELOW_HORIZON
from homeassistant.const import (
    STATE_CLOSED,
    STATE_HOME,
    STATE_LOCKED,
    STATE_NOT_HOME,
    STATE_OFF,
    STATE_ON,
    STATE_OPEN,
    STATE_UNKNOWN,
    STATE_UNLOCKED,
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
            platform: ModuleType = integration.get_platform("reproduce_state")
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
        STATE_LOCKED,
        STATE_ABOVE_HORIZON,
        STATE_OPEN,
        STATE_HOME,
    ):
        return 1
    if state.state in (
        STATE_OFF,
        STATE_UNLOCKED,
        STATE_UNKNOWN,
        STATE_BELOW_HORIZON,
        STATE_CLOSED,
        STATE_NOT_HOME,
    ):
        return 0

    return float(state.state)
