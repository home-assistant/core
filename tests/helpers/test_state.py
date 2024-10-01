"""Test state helpers."""

import asyncio
from unittest.mock import patch

import pytest

from homeassistant.components.lock import LockState
from homeassistant.components.sun import STATE_ABOVE_HORIZON, STATE_BELOW_HORIZON
from homeassistant.const import (
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_CLOSED,
    STATE_HOME,
    STATE_NOT_HOME,
    STATE_OFF,
    STATE_ON,
    STATE_OPEN,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import state

from tests.common import async_mock_service


async def test_call_to_component(hass: HomeAssistant) -> None:
    """Test calls to components state reproduction functions."""
    with patch(
        "homeassistant.components.media_player.reproduce_state.async_reproduce_states"
    ) as media_player_fun:
        media_player_fun.return_value = asyncio.Future()
        media_player_fun.return_value.set_result(None)

        with patch(
            "homeassistant.components.climate.reproduce_state.async_reproduce_states"
        ) as climate_fun:
            climate_fun.return_value = asyncio.Future()
            climate_fun.return_value.set_result(None)

            state_media_player = State("media_player.test", "bad")
            state_climate = State("climate.test", "bad")
            context = "dummy_context"

            await state.async_reproduce_state(
                hass,
                [state_media_player, state_climate],
                context=context,
            )

            media_player_fun.assert_called_once_with(
                hass, [state_media_player], context=context, reproduce_options=None
            )

            climate_fun.assert_called_once_with(
                hass, [state_climate], context=context, reproduce_options=None
            )


async def test_reproduce_with_no_entity(hass: HomeAssistant) -> None:
    """Test reproduce_state with no entity."""
    calls = async_mock_service(hass, "light", SERVICE_TURN_ON)

    await state.async_reproduce_state(hass, State("light.test", "on"))

    await hass.async_block_till_done()

    assert len(calls) == 0
    assert hass.states.get("light.test") is None


async def test_reproduce_turn_on(hass: HomeAssistant) -> None:
    """Test reproduce_state with SERVICE_TURN_ON."""
    calls = async_mock_service(hass, "light", SERVICE_TURN_ON)

    hass.states.async_set("light.test", "off")

    await state.async_reproduce_state(hass, State("light.test", "on"))

    await hass.async_block_till_done()

    assert len(calls) > 0
    last_call = calls[-1]
    assert last_call.domain == "light"
    assert last_call.service == SERVICE_TURN_ON
    assert last_call.data.get("entity_id") == "light.test"


async def test_reproduce_turn_off(hass: HomeAssistant) -> None:
    """Test reproduce_state with SERVICE_TURN_OFF."""
    calls = async_mock_service(hass, "light", SERVICE_TURN_OFF)

    hass.states.async_set("light.test", "on")

    await state.async_reproduce_state(hass, State("light.test", "off"))

    await hass.async_block_till_done()

    assert len(calls) > 0
    last_call = calls[-1]
    assert last_call.domain == "light"
    assert last_call.service == SERVICE_TURN_OFF
    assert last_call.data.get("entity_id") == "light.test"


async def test_reproduce_complex_data(hass: HomeAssistant) -> None:
    """Test reproduce_state with complex service data."""
    calls = async_mock_service(hass, "light", SERVICE_TURN_ON)

    hass.states.async_set("light.test", "off")

    complex_data = [255, 100, 100]

    await state.async_reproduce_state(
        hass, State("light.test", "on", {"rgb_color": complex_data})
    )

    await hass.async_block_till_done()

    assert len(calls) > 0
    last_call = calls[-1]
    assert last_call.domain == "light"
    assert last_call.service == SERVICE_TURN_ON
    assert last_call.data.get("rgb_color") == complex_data


async def test_reproduce_bad_state(hass: HomeAssistant) -> None:
    """Test reproduce_state with bad state."""
    calls = async_mock_service(hass, "light", SERVICE_TURN_ON)

    hass.states.async_set("light.test", "off")

    await state.async_reproduce_state(hass, State("light.test", "bad"))

    await hass.async_block_till_done()

    assert len(calls) == 0
    assert hass.states.get("light.test").state == "off"


async def test_as_number_states(hass: HomeAssistant) -> None:
    """Test state_as_number with states."""
    zero_states = (
        STATE_OFF,
        STATE_CLOSED,
        LockState.UNLOCKED,
        STATE_BELOW_HORIZON,
        STATE_NOT_HOME,
    )
    one_states = (
        STATE_ON,
        STATE_OPEN,
        LockState.LOCKED,
        STATE_ABOVE_HORIZON,
        STATE_HOME,
    )
    for _state in zero_states:
        assert state.state_as_number(State("domain.test", _state, {})) == 0
    for _state in one_states:
        assert state.state_as_number(State("domain.test", _state, {})) == 1


async def test_as_number_coercion(hass: HomeAssistant) -> None:
    """Test state_as_number with number."""
    for _state in ("0", "0.0", 0, 0.0):
        assert state.state_as_number(State("domain.test", _state, {})) == 0.0
    for _state in ("1", "1.0", 1, 1.0):
        assert state.state_as_number(State("domain.test", _state, {})) == 1.0


async def test_as_number_invalid_cases(hass: HomeAssistant) -> None:
    """Test state_as_number with invalid cases."""
    for _state in ("", "foo", "foo.bar", None, False, True, object, object()):
        with pytest.raises(ValueError):
            state.state_as_number(State("domain.test", _state, {}))
