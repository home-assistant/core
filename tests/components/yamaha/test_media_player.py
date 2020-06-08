"""The tests for the Yamaha Media player platform."""
import unittest

import pytest

import homeassistant.components.media_player as mp
from homeassistant.components.yamaha import media_player as yamaha
from homeassistant.components.yamaha.const import DOMAIN
from homeassistant.setup import async_setup_component, setup_component

from tests.async_mock import MagicMock, call, patch
from tests.common import get_test_home_assistant

CONFIG = {"media_player": {"platform": "yamaha", "host": "127.0.0.1"}}


def _create_zone_mock(name, url):
    zone = MagicMock()
    zone.ctrl_url = url
    zone.zone = name
    return zone


class FakeYamahaDevice:
    """A fake Yamaha device."""

    def __init__(self, ctrl_url, name, zones=None):
        """Initialize the fake Yamaha device."""
        self.ctrl_url = ctrl_url
        self.name = name
        self._zones = zones or []

    def zone_controllers(self):
        """Return controllers for all available zones."""
        return self._zones


@pytest.fixture(name="main_zone")
def main_zone_fixture():
    """Mock the main zone."""
    return _create_zone_mock("Main zone", "http://main")


@pytest.fixture(name="device")
def device_fixture(main_zone):
    """Mock the yamaha device."""
    device = FakeYamahaDevice("http://receiver", "Receiver", zones=[main_zone])
    with patch("rxv.RXV", return_value=device):
        yield device


class TestYamahaMediaPlayer(unittest.TestCase):
    """Test the Yamaha media player."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.main_zone = _create_zone_mock("Main zone", "http://main")
        self.device = FakeYamahaDevice(
            "http://receiver", "Receiver", zones=[self.main_zone]
        )

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def enable_output(self, port, enabled):
        """Enable output on a specific port."""
        data = {
            "entity_id": "media_player.yamaha_receiver_main_zone",
            "port": port,
            "enabled": enabled,
        }

        self.hass.services.call(DOMAIN, yamaha.SERVICE_ENABLE_OUTPUT, data, True)

    def select_scene(self, scene):
        """Select Scene."""
        data = {
            "entity_id": "media_player.yamaha_receiver_main_zone",
            "scene": scene,
        }

        self.hass.services.call(DOMAIN, yamaha.SERVICE_SELECT_SCENE, data, True)

    def create_receiver(self, mock_rxv):
        """Create a mocked receiver."""
        mock_rxv.return_value = self.device

        config = {"media_player": {"platform": "yamaha", "host": "127.0.0.1"}}

        assert setup_component(self.hass, mp.DOMAIN, config)
        self.hass.block_till_done()

    @patch("rxv.RXV")
    def test_select_scene(self, mock_rxv):
        """Test selecting scenes."""
        self.create_receiver(mock_rxv)

        self.select_scene("TV Viewing")
        assert self.main_zone.scene == "TV Viewing"

        self.select_scene("BD/DVD Movie Viewing")
        assert self.main_zone.scene == "BD/DVD Movie Viewing"


async def test_enable_output(hass, device, main_zone):
    """Test enable output service."""
    assert await async_setup_component(hass, mp.DOMAIN, CONFIG)
    await hass.async_block_till_done()

    port = "hdmi1"
    enabled = True
    data = {
        "entity_id": "media_player.yamaha_receiver_main_zone",
        "port": port,
        "enabled": enabled,
    }

    await hass.services.async_call(DOMAIN, yamaha.SERVICE_ENABLE_OUTPUT, data, True)

    assert main_zone.enable_output.call_count == 1
    assert main_zone.enable_output.call_args == call(port, enabled)
