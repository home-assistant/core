"""The tests for the Demo Media player platform."""
import unittest
from unittest import mock

from homeassistant.components.media_player import cmus
from homeassistant import const

from tests.common import get_test_home_assistant

entity_id = 'media_player.cmus'


class TestCmusMediaPlayer(unittest.TestCase):
    """Test the media_player module."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    @mock.patch('homeassistant.components.media_player.cmus.CmusDevice')
    def test_password_required_with_host(self, cmus_mock):
        """Test that a password is required when specifying a remote host."""
        fake_config = {
            const.CONF_HOST: 'a_real_hostname',
        }
        self.assertFalse(
            cmus.setup_platform(self.hass, fake_config, mock.MagicMock()))
