"""Test reproduce state for Vacuum."""
from homeassistant.components.vacuum import (
    ATTR_FAN_SPEED,
    SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_SET_FAN_SPEED,
    SERVICE_START,
    SERVICE_STOP,
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_RETURNING,
)
from homeassistant.const import (
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
)
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
    hass.states.async_set("vacuum.entity_idle", STATE_IDLE, {})
    hass.states.async_set("vacuum.entity_returning", STATE_RETURNING, {})
    hass.states.async_set("vacuum.entity_paused", STATE_PAUSED, {})

    turn_on_calls = async_mock_service(hass, "vacuum", SERVICE_TURN_ON)
    turn_off_calls = async_mock_service(hass, "vacuum", SERVICE_TURN_OFF)
    start_calls = async_mock_service(hass, "vacuum", SERVICE_START)
    pause_calls = async_mock_service(hass, "vacuum", SERVICE_PAUSE)
    stop_calls = async_mock_service(hass, "vacuum", SERVICE_STOP)
    return_calls = async_mock_service(hass, "vacuum", SERVICE_RETURN_TO_BASE)
    fan_speed_calls = async_mock_service(hass, "vacuum", SERVICE_SET_FAN_SPEED)

    # These calls should do nothing as entities already in desired state
    await hass.helpers.state.async_reproduce_state(
        [
            State("vacuum.entity_off", STATE_OFF),
            State("vacuum.entity_on", STATE_ON),
            State("vacuum.entity_on_fan", STATE_ON, {ATTR_FAN_SPEED: FAN_SPEED_LOW}),
            State("vacuum.entity_cleaning", STATE_CLEANING),
            State("vacuum.entity_docked", STATE_DOCKED),
            State("vacuum.entity_idle", STATE_IDLE),
            State("vacuum.entity_returning", STATE_RETURNING),
            State("vacuum.entity_paused", STATE_PAUSED),
        ],
    )

    assert len(turn_on_calls) == 0
    assert len(turn_off_calls) == 0
    assert len(start_calls) == 0
    assert len(pause_calls) == 0
    assert len(stop_calls) == 0
    assert len(return_calls) == 0
    assert len(fan_speed_calls) == 0

    # Test invalid state is handled
    await hass.helpers.state.async_reproduce_state(
        [State("vacuum.entity_off", "not_supported")]
    )

    assert "not_supported" in caplog.text
    assert len(turn_on_calls) == 0
    assert len(turn_off_calls) == 0
    assert len(start_calls) == 0
    assert len(pause_calls) == 0
    assert len(stop_calls) == 0
    assert len(return_calls) == 0
    assert len(fan_speed_calls) == 0

    # Make sure correct services are called
    await hass.helpers.state.async_reproduce_state(
        [
            State("vacuum.entity_off", STATE_ON),
            State("vacuum.entity_on", STATE_OFF),
            State("vacuum.entity_on_fan", STATE_ON, {ATTR_FAN_SPEED: FAN_SPEED_HIGH}),
            State("vacuum.entity_cleaning", STATE_PAUSED),
            State("vacuum.entity_docked", STATE_CLEANING),
            State("vacuum.entity_idle", STATE_DOCKED),
            State("vacuum.entity_returning", STATE_CLEANING),
            State("vacuum.entity_paused", STATE_IDLE),
            # Should not raise
            State("vacuum.non_existing", STATE_ON),
        ],
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

    assert len(pause_calls) == 1
    assert pause_calls[0].domain == "vacuum"
    assert pause_calls[0].data == {"entity_id": "vacuum.entity_cleaning"}

    assert len(stop_calls) == 1
    assert stop_calls[0].domain == "vacuum"
    assert stop_calls[0].data == {"entity_id": "vacuum.entity_paused"}

    assert len(return_calls) == 1
    assert return_calls[0].domain == "vacuum"
    assert return_calls[0].data == {"entity_id": "vacuum.entity_idle"}

    assert len(fan_speed_calls) == 1
    assert fan_speed_calls[0].domain == "vacuum"
    assert fan_speed_calls[0].data == {
        "entity_id": "vacuum.entity_on_fan",
        ATTR_FAN_SPEED: FAN_SPEED_HIGH,
    }
