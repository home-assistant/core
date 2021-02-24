"""Configure pytest for Litter-Robot tests."""
from unittest.mock import AsyncMock, MagicMock, patch

from pylitterbot import Robot
import pytest

from homeassistant.components import litterrobot
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .common import CONFIG, ROBOT_DATA

from tests.common import MockConfigEntry


def create_mock_robot(hass):
    """Create a mock Litter-Robot device."""
    robot = Robot(data=ROBOT_DATA)
    robot.start_cleaning = AsyncMock()
    robot.set_power_status = AsyncMock()
    robot.reset_waste_drawer = AsyncMock()
    robot.set_sleep_mode = AsyncMock()
    robot.set_night_light = AsyncMock()
    robot.set_panel_lockout = AsyncMock()
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


async def setup_hub(hass, mock_hub, platform_domain):
    """Load a Litter-Robot platform with the provided hub."""
    entry = MockConfigEntry(
        domain=litterrobot.DOMAIN,
        data=CONFIG[litterrobot.DOMAIN],
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.litterrobot.LitterRobotHub",
        return_value=mock_hub,
    ):
        await hass.config_entries.async_forward_entry_setup(entry, platform_domain)
        await hass.async_block_till_done()
