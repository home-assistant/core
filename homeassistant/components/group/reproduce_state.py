"""Module that groups code required to handle state restore for component."""
from typing import Any, Dict, Iterable, Optional

from homeassistant.core import Context, State
from homeassistant.helpers.state import async_reproduce_state
from homeassistant.helpers.typing import HomeAssistantType

from . import get_entity_ids


async def async_reproduce_states(
    hass: HomeAssistantType,
    states: Iterable[State],
    *,
    context: Optional[Context] = None,
    reproduce_options: Optional[Dict[str, Any]] = None,
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
