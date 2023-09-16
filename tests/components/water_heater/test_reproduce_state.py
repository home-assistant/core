"""Test reproduce state for Water heater."""
import pytest

from homeassistant.components.water_heater import (
    ATTR_AWAY_MODE,
    ATTR_OPERATION_MODE,
    ATTR_TEMPERATURE,
    SERVICE_SET_AWAY_MODE,
    SERVICE_SET_OPERATION_MODE,
    SERVICE_SET_TEMPERATURE,
    STATE_ECO,
    STATE_GAS,
)
from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.state import async_reproduce_state

from tests.common import async_mock_service


async def test_reproducing_states(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test reproducing Water heater states."""
    hass.states.async_set("water_heater.entity_off", STATE_OFF, {})
    hass.states.async_set("water_heater.entity_on", STATE_ON, {ATTR_TEMPERATURE: 45})
    hass.states.async_set("water_heater.entity_away", STATE_ON, {ATTR_AWAY_MODE: True})
    hass.states.async_set("water_heater.entity_gas", STATE_GAS, {})
    hass.states.async_set(
        "water_heater.entity_all",
        STATE_ECO,
        {ATTR_AWAY_MODE: True, ATTR_TEMPERATURE: 45},
    )

    turn_on_calls = async_mock_service(hass, "water_heater", SERVICE_TURN_ON)
    turn_off_calls = async_mock_service(hass, "water_heater", SERVICE_TURN_OFF)
    set_op_calls = async_mock_service(hass, "water_heater", SERVICE_SET_OPERATION_MODE)
    set_temp_calls = async_mock_service(hass, "water_heater", SERVICE_SET_TEMPERATURE)
    set_away_calls = async_mock_service(hass, "water_heater", SERVICE_SET_AWAY_MODE)

    # These calls should do nothing as entities already in desired state
    await async_reproduce_state(
        hass,
        [
            State("water_heater.entity_off", STATE_OFF),
            State("water_heater.entity_on", STATE_ON, {ATTR_TEMPERATURE: 45}),
            State("water_heater.entity_away", STATE_ON, {ATTR_AWAY_MODE: True}),
            State("water_heater.entity_gas", STATE_GAS, {}),
            State(
                "water_heater.entity_all",
                STATE_ECO,
                {ATTR_AWAY_MODE: True, ATTR_TEMPERATURE: 45},
            ),
        ],
    )

    assert len(turn_on_calls) == 0
    assert len(turn_off_calls) == 0
    assert len(set_op_calls) == 0
    assert len(set_temp_calls) == 0
    assert len(set_away_calls) == 0

    # Test invalid state is handled
    await async_reproduce_state(
        hass, [State("water_heater.entity_off", "not_supported")]
    )

    assert "not_supported" in caplog.text
    assert len(turn_on_calls) == 0
    assert len(turn_off_calls) == 0
    assert len(set_op_calls) == 0
    assert len(set_temp_calls) == 0
    assert len(set_away_calls) == 0

    # Make sure correct services are called
    await async_reproduce_state(
        hass,
        [
            State("water_heater.entity_on", STATE_OFF),
            State("water_heater.entity_off", STATE_ON, {ATTR_TEMPERATURE: 45}),
            State("water_heater.entity_all", STATE_ECO, {ATTR_AWAY_MODE: False}),
            State("water_heater.entity_away", STATE_GAS, {}),
            State(
                "water_heater.entity_gas",
                STATE_ECO,
                {ATTR_AWAY_MODE: True, ATTR_TEMPERATURE: 45},
            ),
            # Should not raise
            State("water_heater.non_existing", "on"),
        ],
    )

    assert len(turn_on_calls) == 1
    assert turn_on_calls[0].domain == "water_heater"
    assert turn_on_calls[0].data == {"entity_id": "water_heater.entity_off"}

    assert len(turn_off_calls) == 1
    assert turn_off_calls[0].domain == "water_heater"
    assert turn_off_calls[0].data == {"entity_id": "water_heater.entity_on"}

    valid_op_calls = [
        {"entity_id": "water_heater.entity_away", ATTR_OPERATION_MODE: STATE_GAS},
        {"entity_id": "water_heater.entity_gas", ATTR_OPERATION_MODE: STATE_ECO},
    ]
    assert len(set_op_calls) == 2
    for call in set_op_calls:
        assert call.domain == "water_heater"
        assert call.data in valid_op_calls
        valid_op_calls.remove(call.data)

    valid_temp_calls = [
        {"entity_id": "water_heater.entity_off", ATTR_TEMPERATURE: 45},
        {"entity_id": "water_heater.entity_gas", ATTR_TEMPERATURE: 45},
    ]
    assert len(set_temp_calls) == 2
    for call in set_temp_calls:
        assert call.domain == "water_heater"
        assert call.data in valid_temp_calls
        valid_temp_calls.remove(call.data)

    valid_away_calls = [
        {"entity_id": "water_heater.entity_all", ATTR_AWAY_MODE: False},
        {"entity_id": "water_heater.entity_gas", ATTR_AWAY_MODE: True},
    ]
    assert len(set_away_calls) == 2
    for call in set_away_calls:
        assert call.domain == "water_heater"
        assert call.data in valid_away_calls
        valid_away_calls.remove(call.data)
