"""Configure pytest for Litter-Robot tests."""
from unittest.mock import AsyncMock, MagicMock

from pylitterbot import Robot
import pytest

from homeassistant.components import litterrobot
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .common import ROBOT_DATA


def create_mock_robot(hass):
    """Create a mock Litter-Robot device."""
    robot = Robot(data=ROBOT_DATA)
    robot.start_cleaning = AsyncMock()
    robot.set_power_status = AsyncMock()
    robot.reset_waste_drawer = AsyncMock()
    robot.set_sleep_mode = AsyncMock()
    return robot


@pytest.fixture()
def mock_hub(hass):
    """Mock a Litter-Robot hub."""
    hub = MagicMock(
        hass=hass,
        account=MagicMock(),
        logged_in=True,
        coordinator=MagicMock(spec=DataUpdateCoordinator),
        spec=litterrobot.LitterRobotHub,
    )
    hub.coordinator.last_update_success = True
    hub.account.robots = [create_mock_robot(hass)]
    return hub
