"""Configuration for Sonos tests."""
from asynctest.mock import Mock, patch as patch
import pytest

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.sonos import DOMAIN
from homeassistant.const import CONF_HOSTS

from tests.common import MockConfigEntry


@pytest.fixture(name="config_entry")
def config_entry_fixture():
    """Create a mock Sonos config entry."""
    return MockConfigEntry(domain=DOMAIN, title="Sonos")


@pytest.fixture(name="soco")
def soco_fixture(music_library, speaker_info, dummy_soco_service):
    """Create a mock pysonos SoCo fixture."""
    with patch("pysonos.SoCo", autospec=True) as mock, patch(
        "socket.gethostbyname", return_value="192.168.42.2"
    ):
        mock_soco = mock.return_value
        mock_soco.uid = "RINCON_test"
        mock_soco.music_library = music_library
        mock_soco.get_speaker_info.return_value = speaker_info
        mock_soco.avTransport = dummy_soco_service
        mock_soco.renderingControl = dummy_soco_service
        mock_soco.zoneGroupTopology = dummy_soco_service
        mock_soco.contentDirectory = dummy_soco_service

        yield mock_soco


@pytest.fixture(name="discover", autouse=True)
def discover_fixture(soco):
    """Create a mock pysonos discover fixture."""

    def do_callback(callback, **kwargs):
        callback(soco)

    with patch("pysonos.discover_thread", side_effect=do_callback) as mock:
        yield mock


@pytest.fixture(name="config")
def config_fixture():
    """Create hass config fixture."""
    return {DOMAIN: {MP_DOMAIN: {CONF_HOSTS: ["192.168.42.1"]}}}


@pytest.fixture(name="dummy_soco_service")
def dummy_soco_service_fixture():
    """Create dummy_soco_service fixture."""
    service = Mock()
    service.subscribe = Mock()
    return service


@pytest.fixture(name="music_library")
def music_library_fixture():
    """Create music_library fixture."""
    music_library = Mock()
    music_library.get_sonos_favorites.return_value = []
    return music_library


@pytest.fixture(name="speaker_info")
def speaker_info_fixture():
    """Create speaker_info fixture."""
    return {"zone_name": "Zone A", "model_name": "Model Name"}
