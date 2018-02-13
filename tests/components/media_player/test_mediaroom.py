"""The tests for the mediaroom media_player."""

import unittest

from homeassistant.setup import setup_component
import homeassistant.components.media_player as media_player
from tests.common import (
    assert_setup_component, get_test_home_assistant)


class TestMediaroom(unittest.TestCase):
    """Tests the Mediaroom Component."""

    def setUp(self):
        """Initialize values for this test case class."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that we started."""
        self.hass.stop()

    def test_mediaroom_config(self):
        """Test set up the platform with basic configuration."""
        config = {
            media_player.DOMAIN: {
                'platform': 'mediaroom',
                'name': 'Living Room'
            }
        }
        with assert_setup_component(1, media_player.DOMAIN) as result_config:
            assert setup_component(self.hass, media_player.DOMAIN, config)
        assert result_config[media_player.DOMAIN]
