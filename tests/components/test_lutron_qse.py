"""Tests for Lutron QSE component."""
import unittest
from unittest.mock import MagicMock, patch

from pylutron_qse import qse
from pylutron_qse.devices import Roller

from homeassistant.core import callback
from homeassistant.components import lutron_qse
from homeassistant.helpers import discovery
from tests.common import get_test_home_assistant

TEST_HOST = '192.168.1.10'

VALID_CONFIG = {
    'lutron_qse': {
        'host': TEST_HOST,
        'ignore': ['0x00000001']
    }
}


class TestLutronQSE(unittest.TestCase):
    """Tests the Lutron QSE component."""

    def setUp(self):
        """Initialize values for this test case class."""
        self.hass = get_test_home_assistant()
        self.config = VALID_CONFIG

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @patch.object(qse, 'QSE')
    def test_setup(self, mock_qse_constructor):
        """Test the setup."""
        mock_qse = mock_qse_constructor.return_value = MagicMock()
        mock_qse.connected.return_value = True
        mock_qse.rollers.return_value = []
        response = lutron_qse.setup(self.hass, self.config)

        self.assertTrue(response)
        self.assertTrue(lutron_qse.LUTRON_QSE_INSTANCE in self.hass.data)
        mock_qse_constructor.assert_called_once_with(TEST_HOST)
        mock_qse.connected.assert_called_with()

    @patch.object(qse, 'QSE')
    def test_setup_with_rollers(self, mock_qse_constructor):
        """Test the setup."""
        mock_qse = mock_qse_constructor.return_value = MagicMock()
        mock_qse.connected.return_value = True
        mock_qse.rollers.return_value = [
            Roller(mock_qse, b'0x00000001'), Roller(mock_qse, b'0x00000002')]

        cover_platforms_loaded = []

        @callback
        def load_platform_callback(platform, info):
            cover_platforms_loaded.append(platform)

        discovery.listen_platform(
            self.hass, 'cover', load_platform_callback)

        response = lutron_qse.setup(self.hass, self.config)
        self.assertTrue(response)
        self.hass.block_till_done()
        self.assertIn('lutron_qse', cover_platforms_loaded)
        self.assertNotIn('cover.0x00000001', self.hass.states.entity_ids())
        self.assertIn('cover.0x00000002', self.hass.states.entity_ids())
