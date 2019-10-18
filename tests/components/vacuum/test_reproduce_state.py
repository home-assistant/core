"""Test reproduce state for Vacuum."""
from homeassistant.components.vacuum import (
    ATTR_FAN_SPEED,
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_RETURNING,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import State

from tests.common import async_mock_service

FAN_SPEED_LOW = "low"
FAN_SPEED_HIGH = "high"


async def test_reproducing_states(hass, caplog):
    """Test reproducing Vacuum states."""
    hass.states.async_set("vacuum.entity_off", STATE_OFF, {})
    hass.states.async_set("vacuum.entity_on", STATE_ON, {})
    hass.states.async_set(
        "vacuum.entity_on_fan", STATE_ON, {ATTR_FAN_SPEED: FAN_SPEED_LOW}
    )
    hass.states.async_set("vacuum.entity_cleaning", STATE_CLEANING, {})
    hass.states.async_set("vacuum.entity_docked", STATE_DOCKED, {})
    hass.states.async_set("vacuum.entity_returning", STATE_RETURNING, {})

    turn_on_calls = async_mock_service(hass, "vacuum", "async_turn_on")
    turn_off_calls = async_mock_service(hass, "vacuum", "async_turn_off")
    start_calls = async_mock_service(hass, "vacuum", "async_set_fan_speed")
    return_calls = async_mock_service(hass, "vacuum", "async_return_to_base")
    fan_speed_calls = async_mock_service(hass, "vacuum", "async_set_fan_speed")

    # These calls should do nothing as entities already in desired state
    await hass.helpers.state.async_reproduce_state(
        [
            State("vacuum.entity_off", STATE_OFF),
            State("vacuum.entity_on", STATE_ON),
            State("vacuum.entity_on_fan", STATE_ON, {ATTR_FAN_SPEED: FAN_SPEED_LOW}),
            State("vacuum.entity_cleaning", STATE_CLEANING),
            State("vacuum.entity_docked", STATE_DOCKED),
            State("vacuum.entity_returning", STATE_RETURNING),
        ],
        blocking=True,
    )

    assert len(turn_on_calls) == 0
    assert len(turn_off_calls) == 0
    assert len(start_calls) == 0
    assert len(return_calls) == 0
    assert len(fan_speed_calls) == 0

    # Test invalid state is handled
    await hass.helpers.state.async_reproduce_state(
        [State("vacuum.entity_off", "not_supported")], blocking=True
    )

    assert "not_supported" in caplog.text
    assert len(turn_on_calls) == 0
    assert len(turn_off_calls) == 0
    assert len(start_calls) == 0
    assert len(return_calls) == 0
    assert len(fan_speed_calls) == 0

    # Make sure correct services are called
    await hass.helpers.state.async_reproduce_state(
        [
            State("vacuum.entity_off", STATE_ON),
            State("vacuum.entity_on", STATE_OFF),
            State("vacuum.entity_on_fan", STATE_ON, {ATTR_FAN_SPEED: FAN_SPEED_HIGH}),
            State("vacuum.entity_cleaning", STATE_DOCKED),
            State("vacuum.entity_docked", STATE_CLEANING),
            State("vacuum.entity_returning", STATE_CLEANING),
            # Should not raise
            State("vacuum.non_existing", STATE_ON),
        ],
        blocking=True,
    )

    assert len(turn_on_calls) == 1
    assert turn_on_calls[0].domain == "vacuum"
    assert turn_on_calls[0].data == {"entity_id": "vacuum.entity_off"}

    assert len(turn_off_calls) == 1
    assert turn_off_calls[0].domain == "vacuum"
    assert turn_off_calls[0].data == {"entity_id": "vacuum.entity_on"}

    assert len(start_calls) == 2
    entities = [
        {"entity_id": "vacuum.entity_docked"},
        {"entity_id": "vacuum.entity_returning"},
    ]
    for call in start_calls:
        assert call.domain == "vacuum"
        assert call.data in entities
        entities.remove(call.data)

    assert len(return_calls) == 1
    assert return_calls[0].domain == "vacuum"
    assert return_calls[0].data == {"entity_id": "vacuum.entity_cleaning"}

    assert len(fan_speed_calls) == 1
    assert fan_speed_calls[0].domain == "vacuum"
    assert fan_speed_calls[0].data == {
        "entity_id": "vacuum.entity_on_fan",
        ATTR_FAN_SPEED: FAN_SPEED_HIGH,
    }
