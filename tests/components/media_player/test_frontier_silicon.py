"""The tests for the Demo Media player platform."""
import unittest
from unittest import mock

import logging

from homeassistant.components.media_player.frontier_silicon import FSAPIDevice
from homeassistant.components.media_player import frontier_silicon
from homeassistant import const

from tests.common import get_test_home_assistant

_LOGGER = logging.getLogger(__name__)


class TestFrontierSiliconMediaPlayer(unittest.TestCase):
    """Test the media_player module."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_host_required_with_host(self):
        """Test that a host with a valid url is set when using a conf."""
        fake_config = {
            const.CONF_HOST: 'host_ip',
        }
        result = frontier_silicon.setup_platform(self.hass,
                                                 fake_config, mock.MagicMock())

        self.assertTrue(result)

    def test_invalid_host(self):
        """Test that a host with a valid url is set when using a conf."""
        import requests

        fsapi = FSAPIDevice('INVALID_URL', '1234')
        self.assertRaises(requests.exceptions.MissingSchema, fsapi.update)
