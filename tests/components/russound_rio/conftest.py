"""Test fixtures for Russound RIO integration."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.russound_rio.config_flow import FlowHandler
from homeassistant.components.russound_rio.const import DOMAIN
from homeassistant.components.russound_rio.media_player import RussoundZoneDevice
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_CONFIG = {
    "host": "127.0.0.1",
    "port": 9621,
}

MOCK_DATA = {
    "host": "127.0.0.1",
    "port": 9621,
    "model": "MCA-C5",
}


@pytest.fixture(autouse=True)
def bypass_setup_fixture():
    """Prevent setup."""
    with patch(
        "homeassistant.components.russound_rio.async_setup_entry", return_value=True
    ):
        yield


@pytest.fixture(name="mock_config_entry")
def mock_config_entry_fixture():
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, state=ConfigEntryState.LOADED
    )


@pytest.fixture(name="mock_russound")
def mock_russound_fixture():
    """Mock the Russound RIO library."""
    with patch(
        "homeassistant.components.russound_rio.Russound", autospec=True
    ) as russound_mock:
        russound_mock.enumerate_controllers.return_value = [
            (1, "00:11:22:33:44:55", "MCA-C5")
        ]
        yield russound_mock


@pytest.fixture(name="mock_russound_alt")
def mock_russound_alt_fixture():
    """Mock the Russound RIO library."""
    with patch("aiorussound.Russound", autospec=True) as russound_mock:
        yield russound_mock


@pytest.fixture
def mock_asyncio_timeout():
    """Mock the asyncio timeout."""
    with patch("homeassistant.components.russound_rio.asyncio.timeout") as timeout_mock:
        yield timeout_mock


@pytest.fixture
def mock_zone_id():
    """Mock zone ID."""
    mock = MagicMock()
    mock.device_str.return_value = "zone_1"
    return mock


@pytest.fixture
def mock_sources():
    """Mock sources."""
    return [(1, "Source 1"), (2, "Source 2")]


@pytest.fixture
def media_player(mock_config_entry, mock_russound, mock_zone_id, mock_sources):
    """Create the media player."""
    player = RussoundZoneDevice(
        mock_config_entry, mock_russound, mock_zone_id, "Living Room", mock_sources
    )
    player._russ.get_cached_zone_variable = MagicMock(
        side_effect=lambda zone_id, name, default=None: {
            "name": "Living Room",
            "status": "ON",
            "currentsource": 1,
            "volume": 25,
        }.get(name, default)
    )
    player._russ.get_cached_source_variable = MagicMock(
        side_effect=lambda source_id, name, default=None: {
            "name": "Source 1",
            "songname": "Title",
            "artistname": "Artist",
            "albumname": "Album",
            "coverarturl": "http://image.url",
        }.get(name, default)
    )
    return player


@pytest.fixture
def mock_hass():
    """Mock Home Assistant."""
    return MagicMock(spec=HomeAssistant)


@pytest.fixture
def config_flow(hass: HomeAssistant):
    """Create a config flow instance."""
    flow = FlowHandler()
    flow.hass = hass
    return flow


# @pytest.fixture
# def flow_handler():
#     """Create a config flow instance."""
#     return MagicMock(spec=FlowHandler)
