"""Module that groups code required to handle state restore for component."""
from __future__ import annotations

from typing import Any, Iterable

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
    states_copy = []
    for state in states:
        members = get_entity_ids(hass, state.entity_id)
        for member in members:
            states_copy.append(
                State(
                    member,
                    state.state,
                    state.attributes,
                    last_changed=state.last_changed,
                    last_updated=state.last_updated,
                    context=state.context,
                )
            )
    await async_reproduce_state(
        hass, states_copy, context=context, reproduce_options=reproduce_options
    )
