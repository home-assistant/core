"""Setup the squeezebox tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.squeezebox import const
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac

from tests.common import MockConfigEntry

TEST_HOST = "1.2.3.4"
TEST_PORT = "9000"
TEST_USE_HTTPS = False
SERVER_UUID = "12345678-1234-1234-1234-123456789012"
TEST_MAC = "aa:bb:cc:dd:ee:ff"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.squeezebox.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Add the squeezebox mock config entry to hass."""
    config_entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id=SERVER_UUID,
        data={
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            const.CONF_HTTPS: TEST_USE_HTTPS,
        },
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture
def lms() -> MagicMock:
    """Mock a Lyrion Media Server with one mock player attached."""
    lms = MagicMock()
    player = MagicMock()
    player.player_id = TEST_MAC
    player.name = "Test Player"
    player.power = False
    lms.async_get_players = AsyncMock(return_value=[player])
    lms.async_query = AsyncMock(return_value={"uuid": format_mac(TEST_MAC)})
    return lms
