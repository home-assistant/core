"""Configuration for yamaha_musiccast tests."""
from unittest.mock import patch

from aiomusiccast import MusicCastConnectionException
import pytest


@pytest.fixture(autouse=True)
async def autouse_mock_ssdp(mock_ssdp):
    """Auto use mock_ssdp."""
    yield


@pytest.fixture(autouse=True)
def mock_setup_entry():
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.yamaha_musiccast.async_setup_entry", return_value=True
    ):
        yield


@pytest.fixture
def mock_get_device_info_valid():
    """Mock getting valid device info from musiccast API."""
    with patch(
        "aiomusiccast.MusicCastDevice.get_device_info",
        return_value={"system_id": "1234567890", "model_name": "MC20"},
    ):
        yield


@pytest.fixture
def mock_get_device_info_invalid():
    """Mock getting invalid device info from musiccast API."""
    with patch(
        "aiomusiccast.MusicCastDevice.get_device_info",
        return_value={"type": "no_yamaha"},
    ):
        yield


@pytest.fixture
def mock_get_device_info_exception():
    """Mock raising an unexpected Exception."""
    with patch(
        "aiomusiccast.MusicCastDevice.get_device_info",
        side_effect=Exception("mocked error"),
    ):
        yield


@pytest.fixture
def mock_get_device_info_mc_exception():
    """Mock raising an unexpected Exception."""
    with patch(
        "aiomusiccast.MusicCastDevice.get_device_info",
        side_effect=MusicCastConnectionException("mocked error"),
    ):
        yield


@pytest.fixture
def mock_ssdp_yamaha():
    """Mock that the SSDP detected device is a musiccast device."""
    with patch("aiomusiccast.MusicCastDevice.check_yamaha_ssdp", return_value=True):
        yield


@pytest.fixture
def mock_ssdp_no_yamaha():
    """Mock that the SSDP detected device is not a musiccast device."""
    with patch("aiomusiccast.MusicCastDevice.check_yamaha_ssdp", return_value=False):
        yield


@pytest.fixture
def mock_valid_discovery_information():
    """Mock that the ssdp scanner returns a useful upnp description."""
    with patch(
        "homeassistant.components.ssdp.async_get_discovery_info_by_st",
        return_value=[
            {
                "ssdp_location": "http://127.0.0.1:9000/MediaRenderer/desc.xml",
                "_host": "127.0.0.1",
            }
        ],
    ):
        yield


@pytest.fixture
def mock_empty_discovery_information():
    """Mock that the ssdp scanner returns no upnp description."""
    with patch(
        "homeassistant.components.ssdp.async_get_discovery_info_by_st", return_value=[]
    ):
        yield
