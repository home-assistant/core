"""Configure pytest for Litter-Robot tests."""
from unittest.mock import AsyncMock, MagicMock, patch

import pylitterbot
from pylitterbot import Robot
import pytest

from homeassistant.components import litterrobot

from .common import CONFIG, ROBOT_DATA

from tests.common import MockConfigEntry


def create_mock_robot():
    """Create a mock Litter-Robot device."""
    robot = Robot(data=ROBOT_DATA)
    robot.start_cleaning = AsyncMock()
    robot.set_power_status = AsyncMock()
    robot.reset_waste_drawer = AsyncMock()
    robot.set_sleep_mode = AsyncMock()
    robot.set_night_light = AsyncMock()
    robot.set_panel_lockout = AsyncMock()
    return robot


@pytest.fixture
def mock_account():
    """Mock a Litter-Robot account."""
    account = MagicMock(spec=pylitterbot.Account)
    account.connect = AsyncMock()
    account.refresh_robots = AsyncMock()
    account.robots = [create_mock_robot()]
    return account


async def setup_integration(hass, mock_account, platform_domain=None):
    """Load a Litter-Robot platform with the provided hub."""
    entry = MockConfigEntry(
        domain=litterrobot.DOMAIN,
        data=CONFIG[litterrobot.DOMAIN],
    )
    entry.add_to_hass(hass)

    with patch("pylitterbot.Account", return_value=mock_account), patch(
        "homeassistant.components.litterrobot.PLATFORMS",
        [platform_domain] if platform_domain else [],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
