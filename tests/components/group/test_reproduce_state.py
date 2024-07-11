"""The tests for reproduction of state."""

from asyncio import Future
from unittest.mock import ANY, patch

from homeassistant.components.group.reproduce_state import async_reproduce_states
from homeassistant.core import Context, HomeAssistant, State


async def test_reproduce_group(hass: HomeAssistant) -> None:
    """Test reproduce_state with group."""
    context = Context()

    def clone_state(state, entity_id):
        """Return a cloned state with different entity_id."""
        return State(
            entity_id,
            state.state,
            state.attributes,
            last_changed=state.last_changed,
            last_updated=state.last_updated,
            context=state.context,
        )

    with patch(
        "homeassistant.components.group.reproduce_state.async_reproduce_state"
    ) as fun:
        fun.return_value = Future()
        fun.return_value.set_result(None)

        hass.states.async_set(
            "group.test",
            "off",
            {"entity_id": ["light.test1", "light.test2", "switch.test1"]},
        )
        hass.states.async_set("light.test1", "off")
        hass.states.async_set("light.test2", "off")
        hass.states.async_set("switch.test1", "off")

        state = State("group.test", "on")

        await async_reproduce_states(hass, [state], context=context)

        fun.assert_called_once_with(
            hass,
            ANY,
            context=context,
            reproduce_options=None,
        )
        entities = fun.call_args[0][1]

        assert entities[0].entity_id == "light.test1"
        assert entities[1].entity_id == "light.test2"
        assert entities[2].entity_id == "switch.test1"
