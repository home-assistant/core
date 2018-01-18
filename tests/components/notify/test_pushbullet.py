"""The tests for the pushbullet notification platform."""

import unittest

from homeassistant.setup import setup_component
import homeassistant.components.notify as notify
from tests.common import assert_setup_component, get_test_home_assistant


class TestPushbullet(unittest.TestCase):
    """Test the pushbullet notifications."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_setup(self):
        """Test setup."""
        with assert_setup_component(1) as handle_config:
            assert setup_component(self.hass, 'notify', {
                'notify': {
                    'name': 'test',
                    'platform': 'pushbullet',
                    'api_key': 'MYFAKEKEY', }
            })
        assert handle_config[notify.DOMAIN]

    def test_bad_config(self):
        """Test set up the platform with bad/missing configuration."""
        config = {
            notify.DOMAIN: {
                'name': 'test',
                'platform': 'pushbullet',
            }
        }
        with assert_setup_component(0) as handle_config:
            assert setup_component(self.hass, notify.DOMAIN, config)
        assert not handle_config[notify.DOMAIN]
