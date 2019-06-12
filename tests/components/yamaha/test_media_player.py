"""The tests for the Yamaha Media player platform."""
import unittest
from unittest.mock import patch, MagicMock

from homeassistant.setup import setup_component
import homeassistant.components.media_player as mp
from homeassistant.components.yamaha import media_player as yamaha
from tests.common import get_test_home_assistant


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
        self.zones = zones or []

    def zone_controllers(self):
        """Return controllers for all available zones."""
        return self.zones


class TestYamahaMediaPlayer(unittest.TestCase):
    """Test the Yamaha media player."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.main_zone = _create_zone_mock('Main zone', 'http://main')
        self.device = FakeYamahaDevice(
            'http://receiver', 'Receiver', zones=[self.main_zone])

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def enable_output(self, port, enabled):
        """Enable output on a specific port."""
        data = {
            'entity_id': 'media_player.yamaha_receiver_main_zone',
            'port': port,
            'enabled': enabled
        }

        self.hass.services.call(yamaha.DOMAIN,
                                yamaha.SERVICE_ENABLE_OUTPUT,
                                data,
                                True)

    def create_receiver(self, mock_rxv):
        """Create a mocked receiver."""
        mock_rxv.return_value = self.device

        config = {
            'media_player': {
                'platform': 'yamaha',
                'host': '127.0.0.1'
            }
        }

        assert setup_component(self.hass, mp.DOMAIN, config)

    @patch('rxv.RXV')
    def test_enable_output(self, mock_rxv):
        """Test enabling and disabling outputs."""
        self.create_receiver(mock_rxv)

        self.enable_output('hdmi1', True)
        self.main_zone.enable_output.assert_called_with('hdmi1', True)

        self.enable_output('hdmi2', False)
        self.main_zone.enable_output.assert_called_with('hdmi2', False)
