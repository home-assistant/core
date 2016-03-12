"""The tests for the TCP binary sensor platform."""
from copy import copy
from unittest.mock import patch, Mock

from homeassistant.components.sensor import tcp
from homeassistant.components.binary_sensor import tcp as bin_tcp
from tests.common import get_test_home_assistant
from tests.components.sensor import test_tcp


@patch('homeassistant.components.sensor.tcp.Sensor.update')
def test_setup_platform_valid_config(mock_update):
    """Should check the supplied config and call add_entities with Sensor."""
    add_entities = Mock()
    ret = bin_tcp.setup_platform(None, test_tcp.TEST_CONFIG, add_entities)
    assert ret is None, "setup_platform() should return None if successful."
    assert add_entities.called
    assert isinstance(add_entities.call_args[0][0][0], bin_tcp.BinarySensor)


def test_setup_platform_invalid_config():
    """Should check the supplied config and return False if it is invalid."""
    config = copy(test_tcp.TEST_CONFIG)
    del config[tcp.CONF_HOST]
    assert bin_tcp.setup_platform(None, config, None) is False


class TestTCPBinarySensor():
    """Test the TCP Binary Sensor."""

    def setup_class(cls):
        """Setup things to be run when tests are started."""
        cls.hass = get_test_home_assistant()

    def teardown_class(cls):
        """Stop down everything that was started."""
        cls.hass.stop()

    def test_requires_additional_values(self):
        """Should require the additional config values specified."""
        config = copy(test_tcp.TEST_CONFIG)
        for key in bin_tcp.BinarySensor.required:
            del config[key]
        assert len(config) != len(test_tcp.TEST_CONFIG)
        assert not bin_tcp.BinarySensor.validate_config(config)

    @patch('homeassistant.components.sensor.tcp.Sensor.update')
    def test_is_on_true(self, mock_update):
        """Should return True if _state is the same as value_on."""
        sensor = bin_tcp.BinarySensor(self.hass, test_tcp.TEST_CONFIG)
        sensor._state = test_tcp.TEST_CONFIG[tcp.CONF_VALUE_ON]
        assert sensor.is_on

    @patch('homeassistant.components.sensor.tcp.Sensor.update')
    def test_is_on_false(self, mock_update):
        """Should return False if _state is not the same as value_on."""
        sensor = bin_tcp.BinarySensor(self.hass, test_tcp.TEST_CONFIG)
        sensor._state = "%s abc" % test_tcp.TEST_CONFIG[tcp.CONF_VALUE_ON]
        assert not sensor.is_on
