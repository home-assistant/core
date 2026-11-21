"""Fixtures for the AirLino integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from airlino_api import DEFAULT_PORT, PLAYER_STATE_PLAYING
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.airlino.const import DOMAIN
from homeassistant.const import CONF_API_VERSION, CONF_HOST, CONF_PORT

MAC = "00:23:b1:a4:35:9e"
HOST = "192.0.2.1"


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
        data={CONF_HOST: HOST, CONF_PORT: DEFAULT_PORT, CONF_API_VERSION: "v22"},
        unique_id=MAC,
    )


@pytest.fixture
def mock_airlino_api_class() -> Generator[MagicMock]:
    """Mock the AirLino API client class."""
    with (
        patch("homeassistant.components.airlino.AirlinoApi", autospec=True) as cls,
        patch("homeassistant.components.airlino.config_flow.AirlinoApi", new=cls),
    ):
        api = cls.return_value
        api.async_get_device_info.return_value = {
            "devicename": "Living room",
            "model": "AirLino",
            "firmware": "6.4.1",
        }
        api.async_get_network_info.return_value = {"eth": {"mac": MAC}}
        api.async_get_player_status.return_value = {
            "state": PLAYER_STATE_PLAYING,
            "status": {
                "source": "tidal",
                "elapsedtime": 12,
                "track": {
                    "meta": {"artist": "Artist", "title": "Song"},
                    "totaltime": 180,
                    "image": "http://example.test/cover.jpg",
                },
            },
        }
        api.async_get_master_volume.return_value = 64
        yield cls


@pytest.fixture
def mock_airlino_api(mock_airlino_api_class: MagicMock) -> MagicMock:
    """Return the mocked AirLino API client."""
    return mock_airlino_api_class.return_value
