"""Fixtures for the Neato tests."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

from pybotvac import Robot
import pytest

from homeassistant.components.neato.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a Neato config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="mock-user-id",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
            },
        },
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_robot() -> MagicMock:
    """Return a mocked docked Neato robot."""
    robot = MagicMock(spec=Robot)
    robot.serial = "mock-serial"
    robot.name = "Mock Robot"
    robot.has_persistent_maps = False
    robot.state = {
        "state": 1,
        "details": {
            "isCharging": False,
            "isDocked": True,
            "isScheduleEnabled": False,
        },
    }
    robot.get_general_info.return_value.json.return_value = {
        "data": {
            "battery": {"vendor": "Neato"},
            "model": "botvacD7",
            "firmware": "4.5.3",
        }
    }
    return robot


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_robot: MagicMock,
) -> AsyncGenerator[None]:
    """Set up the Neato integration with one robot."""
    with (
        patch(
            "homeassistant.components.neato.PLATFORMS",
            [Platform.SWITCH, Platform.VACUUM],
        ),
        patch("homeassistant.components.neato.async_get_config_entry_implementation"),
        patch("homeassistant.components.neato.OAuth2Session") as oauth_session,
        patch("homeassistant.components.neato.api.ConfigEntryAuth"),
        patch("homeassistant.components.neato.Account") as account,
    ):
        oauth_session.return_value.async_ensure_token_valid = AsyncMock()
        account.return_value.unique_id = "mock-user-id"
        account.return_value.robots = {mock_robot}
        account.return_value.persistent_maps = {}
        account.return_value.maps = {}
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        yield
