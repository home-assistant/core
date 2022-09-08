"""Configure pytest for Litter-Robot tests."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from pylitterbot import Account, LitterRobot3, Robot
from pylitterbot.exceptions import InvalidCommandException
import pytest

from homeassistant.components import litterrobot
from homeassistant.core import HomeAssistant

from .common import CONFIG, ROBOT_DATA

from tests.common import MockConfigEntry


def create_mock_robot(
    robot_data: dict | None = None, side_effect: Any | None = None
) -> Robot:
    """Create a mock Litter-Robot device."""
    if not robot_data:
        robot_data = {}

    robot = LitterRobot3(data={**ROBOT_DATA, **robot_data})
    robot.start_cleaning = AsyncMock(side_effect=side_effect)
    robot.set_power_status = AsyncMock(side_effect=side_effect)
    robot.reset_waste_drawer = AsyncMock(side_effect=side_effect)
    robot.set_sleep_mode = AsyncMock(side_effect=side_effect)
    robot.set_night_light = AsyncMock(side_effect=side_effect)
    robot.set_panel_lockout = AsyncMock(side_effect=side_effect)
    robot.set_wait_time = AsyncMock(side_effect=side_effect)
    robot.refresh = AsyncMock(side_effect=side_effect)
    return robot


def create_mock_account(
    robot_data: dict | None = None,
    side_effect: Any | None = None,
    skip_robots: bool = False,
) -> MagicMock:
    """Create a mock Litter-Robot account."""
    account = MagicMock(spec=Account)
    account.connect = AsyncMock()
    account.refresh_robots = AsyncMock()
    account.robots = [] if skip_robots else [create_mock_robot(robot_data, side_effect)]
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
def mock_account_with_sleeping_robot() -> MagicMock:
    """Mock a Litter-Robot account with a sleeping robot."""
    return create_mock_account({"sleepModeActive": "102:00:00"})


@pytest.fixture
def mock_account_with_sleep_disabled_robot() -> MagicMock:
    """Mock a Litter-Robot account with a robot that has sleep mode disabled."""
    return create_mock_account({"sleepModeActive": "0"})


@pytest.fixture
def mock_account_with_error() -> MagicMock:
    """Mock a Litter-Robot account with error."""
    return create_mock_account({"unitStatus": "BR"})


@pytest.fixture
def mock_account_with_side_effects() -> MagicMock:
    """Mock a Litter-Robot account with side effects."""
    return create_mock_account(
        side_effect=InvalidCommandException("Invalid command: oops")
    )


async def setup_integration(
    hass: HomeAssistant, mock_account: MagicMock, platform_domain: str | None = None
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
        "homeassistant.components.litterrobot.PLATFORMS_BY_TYPE",
        {Robot: (platform_domain,)} if platform_domain else {},
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
