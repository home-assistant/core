"""Test for Neato vacuum platform."""
from unittest.mock import patch

from homeassistant.components.neato.vacuum import NeatoConnectedVacuum
from homeassistant.components.vacuum import STATE_CLEANING, STATE_DOCKED, STATE_ERROR
from homeassistant.const import STATE_IDLE, STATE_PAUSED


@patch("homeassistant.components.neato.hub.NeatoHub")
@patch("pybotvac.robot.Robot")
def test_update_state_paused(robot_mock, neato_mock) -> None:
    """Test the update function for paused state."""

    vacuum = NeatoConnectedVacuum(
        neato=neato_mock, robot=robot_mock, mapdata=None, persistent_maps=None
    )

    robot_mock.state = {
        "state": 3,
        "details": {"charge": 90},
    }

    vacuum.update()
    assert vacuum._attr_available is True
    assert vacuum._attr_battery_level == 90
    assert vacuum._attr_state == STATE_PAUSED


@patch("homeassistant.components.neato.hub.NeatoHub")
@patch("pybotvac.robot.Robot")
def test_update_state_error(robot_mock, neato_mock) -> None:
    """Test the update function for error state."""

    vacuum = NeatoConnectedVacuum(
        neato=neato_mock, robot=robot_mock, mapdata=None, persistent_maps=None
    )

    robot_mock.state = {
        "state": 4,
        "details": {"charge": 90},
        "error": "ui_error_brush_stuck",
    }

    vacuum.update()
    assert vacuum._attr_state == STATE_ERROR
    assert vacuum._status_state == "Brush stuck"


@patch("homeassistant.components.neato.hub.NeatoHub")
@patch("pybotvac.robot.Robot")
def test_update_state_docked(robot_mock, neato_mock) -> None:
    """Test the update function for docked state."""

    vacuum = NeatoConnectedVacuum(
        neato=neato_mock, robot=robot_mock, mapdata=None, persistent_maps=None
    )

    # Charging
    robot_mock.state = {
        "state": 1,
        "details": {"charge": 10, "isCharging": True},
    }
    vacuum.update()
    assert vacuum._attr_state == STATE_DOCKED
    assert vacuum._status_state == "Charging"

    # Docked
    robot_mock.state = {
        "state": 1,
        "details": {"charge": 100, "isCharging": False, "isDocked": True},
    }
    vacuum.update()
    assert vacuum._attr_state == STATE_DOCKED
    assert vacuum._status_state == "Docked"

    # If there is an alert, set it in _status_state
    robot_mock.state = {
        "state": 1,
        "details": {"charge": 100, "isCharging": False, "isDocked": True},
        "alert": "dustbin_full",
    }
    vacuum.update()
    assert vacuum._attr_state == STATE_DOCKED
    assert vacuum._status_state == "Please empty dust bin"


@patch("homeassistant.components.neato.hub.NeatoHub")
@patch("pybotvac.robot.Robot")
def test_update_state_idle(robot_mock, neato_mock) -> None:
    """Test the update function for idle state."""

    vacuum = NeatoConnectedVacuum(
        neato=neato_mock, robot=robot_mock, mapdata=None, persistent_maps=None
    )

    # Idle
    robot_mock.state = {
        "state": 1,
        "details": {"charge": 100, "isCharging": False, "isDocked": False},
    }
    vacuum.update()
    assert vacuum._attr_state == STATE_IDLE
    assert vacuum._status_state == "Stopped"

    # If there is an alert, set it in _status_state
    robot_mock.state = {
        "state": 1,
        "details": {"charge": 10, "isCharging": False, "isDocked": True},
        "alert": "ui_alert_busy_charging",
    }
    vacuum.update()
    assert vacuum._attr_state == STATE_DOCKED
    assert vacuum._status_state == "Busy charging"


@patch("homeassistant.components.neato.hub.NeatoHub")
@patch("pybotvac.robot.Robot")
def test_update_state_cleaning(robot_mock, neato_mock) -> None:
    """Test the update function for idle state."""

    vacuum = NeatoConnectedVacuum(
        neato=neato_mock, robot=robot_mock, mapdata=None, persistent_maps=None
    )

    # Cleaning
    robot_mock.state = {
        "state": 2,
        "details": {
            "charge": 80,
        },
        "action": 1,
        "cleaning": {"mode": 1},
    }
    vacuum.update()
    assert vacuum._attr_state == STATE_CLEANING
    assert vacuum._status_state == "Eco House Cleaning"

    # Cleaning (with boundary info)
    robot_mock.state = {
        "state": 2,
        "details": {
            "charge": 80,
        },
        "action": 2,
        "cleaning": {"mode": 2, "boundary": {"name": "Living Room"}},
    }
    vacuum.update()
    assert vacuum._attr_state == STATE_CLEANING
    assert vacuum._status_state == "Turbo Spot Cleaning Living Room"

    # If there is an alert, set it in _status_state
    vacuum._attr_state = None
    robot_mock.state = {
        "state": 2,
        "details": {
            "charge": 80,
        },
        "alert": "maint_brush_change",
    }
    vacuum.update()
    assert vacuum._attr_state is None
    assert vacuum._status_state == "Change the brush"
