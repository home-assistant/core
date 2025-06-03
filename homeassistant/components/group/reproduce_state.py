"""Module that groups code required to handle state restore for component."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from homeassistant.core import Context, HomeAssistant, State
from homeassistant.helpers.state import async_reproduce_state

from . import get_entity_ids


async def async_reproduce_states(
    hass: HomeAssistant,
    states: Iterable[State],
    *,
    context: Context | None = None,
    reproduce_options: dict[str, Any] | None = None,
) -> None:
    """Reproduce component states."""
    states_copy = [
        State(
            member,
            state.state,
            state.attributes,
            last_changed=state.last_changed,
            last_reported=state.last_reported,
            last_updated=state.last_updated,
            context=state.context,
        )
        for state in states
        for member in get_entity_ids(hass, state.entity_id)
    ]
    await async_reproduce_state(
        hass, states_copy, context=context, reproduce_options=reproduce_options
    )
