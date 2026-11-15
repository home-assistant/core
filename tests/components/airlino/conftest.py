"""Fixtures for the AirLino integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from airlino_api import DEFAULT_PORT, PLAYER_STATE_STOPPED
import pytest

from homeassistant.components.airlino.const import DOMAIN
from homeassistant.const import CONF_API_VERSION, CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock entry setup to prevent post-flow network requests."""
    with patch(
        "homeassistant.components.airlino.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a configured AirLino config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Living room",
        data={CONF_HOST: "192.0.2.1", CONF_PORT: DEFAULT_PORT, CONF_API_VERSION: "v22"},
        unique_id="00:11:22:33:44:55",
    )


@pytest.fixture
def mock_airlino_api() -> Generator[MagicMock]:
    """Mock the AirLino API client used by the config entry."""
    with patch("homeassistant.components.airlino.AirlinoApi", autospec=True) as cls:
        api = cls.return_value
        api.async_get_device_info.return_value = {
            "devicename": "Living room",
            "model": "AirLino",
            "firmware": "6.4.1",
        }
        api.async_get_player_status.return_value = {
            "state": PLAYER_STATE_STOPPED,
            "status": {},
        }
        api.async_get_master_volume.return_value = 50
        yield api
