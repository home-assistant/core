"""Test reproduce state for Vacuum."""

import pytest
from pytest_homeassistant.common import async_mock_service

from homeassistant.components.vacuum import (
    ATTR_FAN_SPEED,
    DOMAIN,
    SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_SET_FAN_SPEED,
    SERVICE_START,
    SERVICE_STOP,
    VacuumActivity,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.state import async_reproduce_state

FAN_SPEED_LOW = "low"
FAN_SPEED_HIGH = "high"


async def test_reproducing_states(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test reproducing Vacuum states."""
    hass.states.async_set(
        "vacuum.entity_cleaning_fan",
        VacuumActivity.CLEANING,
        {ATTR_FAN_SPEED: FAN_SPEED_LOW},
    )
    hass.states.async_set("vacuum.entity_cleaning", VacuumActivity.CLEANING, {})
    hass.states.async_set("vacuum.entity_docked", VacuumActivity.DOCKED, {})
    hass.states.async_set("vacuum.entity_idle", VacuumActivity.IDLE, {})
    hass.states.async_set("vacuum.entity_returning", VacuumActivity.RETURNING, {})
    hass.states.async_set("vacuum.entity_paused", VacuumActivity.PAUSED, {})

    start_calls = async_mock_service(hass, DOMAIN, SERVICE_START)
    pause_calls = async_mock_service(hass, DOMAIN, SERVICE_PAUSE)
    stop_calls = async_mock_service(hass, DOMAIN, SERVICE_STOP)
    return_calls = async_mock_service(hass, DOMAIN, SERVICE_RETURN_TO_BASE)
    fan_speed_calls = async_mock_service(hass, DOMAIN, SERVICE_SET_FAN_SPEED)

    # These calls should do nothing as entities already in desired state
    await async_reproduce_state(
        hass,
        [
            State(
                "vacuum.entity_cleaning_fan",
                VacuumActivity.CLEANING,
                {ATTR_FAN_SPEED: FAN_SPEED_LOW},
            ),
            State("vacuum.entity_cleaning", VacuumActivity.CLEANING),
            State("vacuum.entity_docked", VacuumActivity.DOCKED),
            State("vacuum.entity_idle", VacuumActivity.IDLE),
            State("vacuum.entity_returning", VacuumActivity.RETURNING),
            State("vacuum.entity_paused", VacuumActivity.PAUSED),
        ],
    )

    assert len(start_calls) == 0
    assert len(pause_calls) == 0
    assert len(stop_calls) == 0
    assert len(return_calls) == 0
    assert len(fan_speed_calls) == 0

    # Test invalid states are handled, including on/off which vacuums no longer have
    await async_reproduce_state(
        hass,
        [
            State("vacuum.entity_docked", "not_supported"),
            State("vacuum.entity_idle", STATE_ON),
            State("vacuum.entity_cleaning", STATE_OFF),
        ],
    )

    assert (
        "Invalid state specified for vacuum.entity_docked: not_supported" in caplog.text
    )
    assert "Invalid state specified for vacuum.entity_idle: on" in caplog.text
    assert "Invalid state specified for vacuum.entity_cleaning: off" in caplog.text
    assert len(start_calls) == 0
    assert len(pause_calls) == 0
    assert len(stop_calls) == 0
    assert len(return_calls) == 0
    assert len(fan_speed_calls) == 0

    # Make sure correct services are called
    await async_reproduce_state(
        hass,
        [
            State(
                "vacuum.entity_cleaning_fan",
                VacuumActivity.CLEANING,
                {ATTR_FAN_SPEED: FAN_SPEED_HIGH},
            ),
            State("vacuum.entity_cleaning", VacuumActivity.PAUSED),
            State("vacuum.entity_docked", VacuumActivity.CLEANING),
            State("vacuum.entity_idle", VacuumActivity.DOCKED),
            State("vacuum.entity_returning", VacuumActivity.CLEANING),
            State("vacuum.entity_paused", VacuumActivity.IDLE),
            # Should not raise
            State("vacuum.non_existing", VacuumActivity.CLEANING),
        ],
    )

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
        "entity_id": "vacuum.entity_cleaning_fan",
        ATTR_FAN_SPEED: FAN_SPEED_HIGH,
    }
