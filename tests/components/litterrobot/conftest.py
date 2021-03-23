"""Configure pytest for Litter-Robot tests."""
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

from pylitterbot import Account, Robot
from pylitterbot.exceptions import InvalidCommandException
import pytest

from homeassistant.components import litterrobot
from homeassistant.core import HomeAssistant

from .common import CONFIG, ROBOT_DATA

from tests.common import MockConfigEntry


def create_mock_robot(robot_data: Optional[dict] = None):
    """Create a mock Litter-Robot device."""
    if not robot_data:
        robot_data = {}

    robot = Robot(data={**ROBOT_DATA, **robot_data})
    robot.start_cleaning = AsyncMock()
    robot.set_power_status = AsyncMock()
    robot.reset_waste_drawer = AsyncMock()
    robot.set_sleep_mode = AsyncMock()
    robot.set_night_light = AsyncMock()
    robot.set_panel_lockout = AsyncMock()
    return robot


def create_mock_account(robot_data: Optional[dict] = None):
    """Create a mock Litter-Robot account."""
    account = MagicMock(spec=Account)
    account.connect = AsyncMock()
    account.refresh_robots = AsyncMock()
    account.robots = [create_mock_robot(robot_data)]
    return account


@pytest.fixture
def mock_account() -> MagicMock:
    """Mock a Litter-Robot account."""
    return create_mock_account()


@pytest.fixture
def mock_account_with_no_robots() -> MagicMock:
    """Mock a Litter-Robot account."""
    return create_mock_account(skip_robots=True)


@pytest.fixture
def mock_account_with_error() -> MagicMock:
    """Mock a Litter-Robot account with error."""
    return create_mock_account({"unitStatus": "BR"})


async def setup_integration(
    hass: HomeAssistant, mock_account: MagicMock, platform_domain: Optional[str] = None
) -> MockConfigEntry:
    """Load a Litter-Robot platform with the provided hub."""
    entry = MockConfigEntry(
        domain=litterrobot.DOMAIN,
        data=CONFIG[litterrobot.DOMAIN],
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.litterrobot.hub.Account", return_value=mock_account
    ), patch(
        "homeassistant.components.litterrobot.PLATFORMS",
        [platform_domain] if platform_domain else [],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
