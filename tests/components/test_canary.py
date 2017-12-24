"""The tests for the Canary component."""
import unittest
from unittest.mock import patch, MagicMock, PropertyMock

import homeassistant.components.canary as canary
from homeassistant import setup
from tests.common import (
    get_test_home_assistant)


def mock_device(device_id, name, is_online=True):
    """Mock Canary Device class."""
    device = MagicMock()
    type(device).device_id = PropertyMock(return_value=device_id)
    type(device).name = PropertyMock(return_value=name)
    type(device).is_online = PropertyMock(return_value=is_online)
    return device


def mock_location(name, is_celsius=True, devices=[]):
    """Mock Canary Location class."""
    location = MagicMock()
    type(location).name = PropertyMock(return_value=name)
    type(location).is_celsius = PropertyMock(return_value=is_celsius)
    type(location).devices = PropertyMock(return_value=devices)
    return location


def mock_reading(sensor_type, sensor_value):
    """Mock Canary Reading class."""
    reading = MagicMock()
    type(reading).sensor_type = PropertyMock(return_value=sensor_type)
    type(reading).value = PropertyMock(return_value=sensor_value)
    return reading


class TestCanary(unittest.TestCase):
    """Tests the Canary component."""

    def setUp(self):
        """Initialize values for this test case class."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    @patch('homeassistant.components.canary.CanaryData.update')
    @patch('canary.api.Api.login')
    def test_setup_with_valid_config(self, mock_login, mock_update):
        """Test setup component."""
        config = {
            "canary": {
                "username": "foo@bar.org",
                "password": "bar",
            }
        }

        self.assertTrue(
            setup.setup_component(self.hass, canary.DOMAIN, config))

        mock_update.assert_called_once_with()
        mock_login.assert_called_once_with()

    def test_setup_with_missing_password(self):
        """Test setup component."""
        config = {
            "canary": {
                "username": "foo@bar.org",
            }
        }

        self.assertFalse(
            setup.setup_component(self.hass, canary.DOMAIN, config))

    def test_setup_with_missing_username(self):
        """Test setup component."""
        config = {
            "canary": {
                "password": "bar",
            }
        }

        self.assertFalse(
            setup.setup_component(self.hass, canary.DOMAIN, config))
