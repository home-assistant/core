"""The tests for the apprise notification platform."""
import unittest
from unittest.mock import patch

from apprise import Apprise
import requests_mock

from homeassistant.setup import setup_component
import homeassistant.components.notify as notify
from tests.common import assert_setup_component, get_test_home_assistant


class TestApprise(unittest.TestCase):
    """Tests the Apprise Component."""

    def setUp(self):
        """Initialize values for this test case class."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that we started."""
        self.hass.stop()

    @patch.object(Apprise, "notify", return_value=True)
    def test_apprise_config(self, mock__get_data):
        """Test setup."""
        config = {
            notify.DOMAIN: {"name": "test", "platform": "apprise", "url": "dbus://"}
        }
        with assert_setup_component(1) as handle_config:
            assert setup_component(self.hass, notify.DOMAIN, config)
        assert handle_config[notify.DOMAIN]

    def test_apprise_config_bad(self):
        """Test set up the platform with bad/missing configuration."""
        config = {
            notify.DOMAIN: {
                "name": "test",
                "platform": "apprise",
                # Expects a list
                "url": 1,
            }
        }
        with assert_setup_component(0) as handle_config:
            assert setup_component(self.hass, notify.DOMAIN, config)
        assert not handle_config[notify.DOMAIN]

    @requests_mock.Mocker()
    @patch.object(Apprise, "notify", return_value=True)
    def test_apprise_push_default(self, mock, mock__get_data):
        """Test simple apprise push."""
        config = {
            notify.DOMAIN: {"name": "test", "platform": "apprise", "url": "windows://"}
        }
        with assert_setup_component(1) as handle_config:
            assert setup_component(self.hass, notify.DOMAIN, config)
        assert handle_config[notify.DOMAIN]
        data = {"title": "Test Title", "message": "Test Message"}
        assert not self.hass.services.call(notify.DOMAIN, "test", data)
        self.hass.block_till_done()
