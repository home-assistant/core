from unittest.mock import patch

import pytest

from homeassistant.components.cosa.cosa_manager import CosaManager


@pytest.fixture
def cosa_manager():
    """Fixture for creating a CosaManager instance."""
    with patch("homeassistant.components.cosa.cosa_manager.Api") as MockApi:
        mock_api = MockApi.return_value
        mock_api.status.return_value = True
        mock_api.getEndpoints.return_value = [{"id": "home123"}]
        mock_api.getEndpoint.return_value = {
            "homeTemperature": 20,
            "awayTemperature": 15,
            "sleepTemperature": 18,
            "customTemperature": 22,
            "mode": "manual",
            "option": "custom",
        }
        mock_api.setTargetTemperatures.return_value = True
        mock_api.enableCustomMode.return_value = True
        mock_api.disable.return_value = True
        mock_api.enableSchedule.return_value = True
        return CosaManager("username", "password")


def test_get_connection_status(cosa_manager) -> None:
    """Test the get_connection_status method."""
    assert cosa_manager.getConnectionStatus() is True


def test_get_home_id(cosa_manager) -> None:
    """Test the getHomeId method."""
    assert cosa_manager.getHomeId() == "home123"


def test_get_current_status(cosa_manager) -> None:
    """Test the getCurrentStatus method."""
    status = cosa_manager.getCurrentStatus()
    assert status is not None
    assert status["homeTemperature"] == 20


def test_set_temperature(cosa_manager) -> None:
    """Test the setTemperature method."""
    assert cosa_manager.setTemperature(22) is True


def test_turn_off(cosa_manager) -> None:
    """Test the turnOff method."""
    assert cosa_manager.turnOff() is True


def test_enable_schedule(cosa_manager) -> None:
    """Test the enableSchedule method."""
    assert cosa_manager.enableSchedule() is True
