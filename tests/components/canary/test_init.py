"""The tests for the Canary component."""
import unittest

from homeassistant import setup
import homeassistant.components.canary as canary

from tests.async_mock import MagicMock, PropertyMock, patch
from tests.common import get_test_home_assistant


def mock_device(device_id, name, is_online=True, device_type_name=None):
    """Mock Canary Device class."""
    device = MagicMock()
    type(device).device_id = PropertyMock(return_value=device_id)
    type(device).name = PropertyMock(return_value=name)
    type(device).is_online = PropertyMock(return_value=is_online)
    type(device).device_type = PropertyMock(
        return_value={"id": 1, "name": device_type_name}
    )
    return device


def mock_location(name, is_celsius=True, devices=None):
    """Mock Canary Location class."""
    location = MagicMock()
    type(location).name = PropertyMock(return_value=name)
    type(location).is_celsius = PropertyMock(return_value=is_celsius)
    type(location).devices = PropertyMock(return_value=devices or [])
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

    @patch("homeassistant.components.canary.CanaryData.update")
    @patch("canary.api.Api.login")
    def test_setup_with_valid_config(self, mock_login, mock_update):
        """Test setup component."""
        config = {"canary": {"username": "foo@bar.org", "password": "bar"}}

        assert setup.setup_component(self.hass, canary.DOMAIN, config)

        mock_update.assert_called_once_with()
        mock_login.assert_called_once_with()

    def test_setup_with_missing_password(self):
        """Test setup component."""
        config = {"canary": {"username": "foo@bar.org"}}

        assert not setup.setup_component(self.hass, canary.DOMAIN, config)

    def test_setup_with_missing_username(self):
        """Test setup component."""
        config = {"canary": {"password": "bar"}}

        assert not setup.setup_component(self.hass, canary.DOMAIN, config)
