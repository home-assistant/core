"""The tests for the TCP binary sensor platform."""
import unittest
from unittest.mock import patch, Mock

from homeassistant.setup import setup_component
from homeassistant.components.binary_sensor import tcp as bin_tcp
from homeassistant.components.sensor import tcp
from tests.common import (get_test_home_assistant, assert_setup_component)
from tests.components.sensor import test_tcp


class TestTCPBinarySensor(unittest.TestCase):
    """Test the TCP Binary Sensor."""

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop down everything that was started."""
        self.hass.stop()

    def test_setup_platform_valid_config(self):
        """Check a valid configuration."""
        with assert_setup_component(0, 'binary_sensor'):
            assert setup_component(
                self.hass, 'binary_sensor', test_tcp.TEST_CONFIG)

    def test_setup_platform_invalid_config(self):
        """Check the invalid configuration."""
        with assert_setup_component(0):
            assert setup_component(self.hass, 'binary_sensor', {
                'binary_sensor': {
                    'platform': 'tcp',
                    'porrt': 1234,
                }
            })

    @patch('homeassistant.components.sensor.tcp.TcpSensor.update')
    def test_setup_platform_devices(self, mock_update):
        """Check the supplied config and call add_entities with sensor."""
        add_entities = Mock()
        ret = bin_tcp.setup_platform(None, test_tcp.TEST_CONFIG, add_entities)
        assert ret is None
        assert add_entities.called
        assert isinstance(
            add_entities.call_args[0][0][0], bin_tcp.TcpBinarySensor)

    @patch('homeassistant.components.sensor.tcp.TcpSensor.update')
    def test_is_on_true(self, mock_update):
        """Check the return that _state is value_on."""
        sensor = bin_tcp.TcpBinarySensor(
            self.hass, test_tcp.TEST_CONFIG['sensor'])
        sensor._state = test_tcp.TEST_CONFIG['sensor'][tcp.CONF_VALUE_ON]
        print(sensor._state)
        assert sensor.is_on

    @patch('homeassistant.components.sensor.tcp.TcpSensor.update')
    def test_is_on_false(self, mock_update):
        """Check the return that _state is not the same as value_on."""
        sensor = bin_tcp.TcpBinarySensor(
            self.hass, test_tcp.TEST_CONFIG['sensor'])
        sensor._state = '{} abc'.format(
            test_tcp.TEST_CONFIG['sensor'][tcp.CONF_VALUE_ON])
        assert not sensor.is_on
