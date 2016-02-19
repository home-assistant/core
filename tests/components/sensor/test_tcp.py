"""
tests.components.sensor.tcp
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests TCP sensor.
"""
import socket
from copy import copy

from unittest.mock import patch

from homeassistant.components.sensor import tcp
from tests.common import get_test_home_assistant


TEST_CONFIG = {
    tcp.CONF_NAME: "test_name",
    tcp.CONF_HOST: "test_host",
    tcp.CONF_PORT: 12345,
    tcp.CONF_TIMEOUT: tcp.DEFAULT_TIMEOUT + 1,
    tcp.CONF_PAYLOAD: "test_payload",
    tcp.CONF_UNIT: "test_unit",
    tcp.CONF_VALUE_TEMPLATE: "test_template",
    tcp.CONF_VALUE_ON: "test_on",
    tcp.CONF_BUFFER_SIZE: tcp.DEFAULT_BUFFER_SIZE + 1
}
KEYS_AND_DEFAULTS = {
    tcp.CONF_NAME: None,
    tcp.CONF_TIMEOUT: tcp.DEFAULT_TIMEOUT,
    tcp.CONF_UNIT: None,
    tcp.CONF_VALUE_TEMPLATE: None,
    tcp.CONF_VALUE_ON: None,
    tcp.CONF_BUFFER_SIZE: tcp.DEFAULT_BUFFER_SIZE
}


# class TestTCPSensor(unittest.TestCase):
class TestTCPSensor():
    """ Test the TCP Sensor. """

    def setup_class(cls):
        cls.hass = get_test_home_assistant()

    def teardown_class(cls):
        cls.hass.stop()

    @patch("homeassistant.components.sensor.tcp.Sensor.update")
    def test_config_valid_keys(self, *args):
        """
        Should store valid keys in _config.
        """
        sensor = tcp.Sensor(self.hass, TEST_CONFIG)
        for key in TEST_CONFIG:
            assert key in sensor._config

    def test_validate_config_valid_keys(self):
        """
        Should return True when provided with the correct keys.
        """
        assert tcp.Sensor.validate_config(TEST_CONFIG)

    @patch("homeassistant.components.sensor.tcp.Sensor.update")
    def test_config_invalid_keys(self, *args):
        """
        Shouldn't store invalid keys in _config.
        """
        config = copy(TEST_CONFIG)
        config.update({
            "a": "test_a",
            "b": "test_b",
            "c": "test_c"
        })
        sensor = tcp.Sensor(self.hass, config)
        for invalid_key in tuple("abc"):
            assert invalid_key not in sensor._config

    @patch("homeassistant.components.sensor.tcp.Sensor.update")
    def test_validate_config_invalid_keys(self, *args):
        """
        Should return True when provided with the correct keys plus some extra.
        """
        config = copy(TEST_CONFIG)
        config.update({
            "a": "test_a",
            "b": "test_b",
            "c": "test_c"
        })
        assert tcp.Sensor.validate_config(config)

    @patch("homeassistant.components.sensor.tcp.Sensor.update")
    def test_config_uses_defaults(self, *args):
        """
        Should use defaults where appropriate.
        """
        config = copy(TEST_CONFIG)
        for key in KEYS_AND_DEFAULTS.keys():
            del config[key]
        sensor = tcp.Sensor(self.hass, config)
        for key, default in KEYS_AND_DEFAULTS.items():
            assert sensor._config[key] == default

    def test_validate_config_missing_defaults(self):
        """
        Should return True when defaulted keys are not provided.
        """
        config = copy(TEST_CONFIG)
        for key in KEYS_AND_DEFAULTS.keys():
            del config[key]
        assert tcp.Sensor.validate_config(config)

    def test_validate_config_missing_required(self):
        """
        Should return False when required config items are missing.
        """
        for key in TEST_CONFIG:
            if key in KEYS_AND_DEFAULTS:
                continue
            config = copy(TEST_CONFIG)
            del config[key]
            assert not tcp.Sensor.validate_config(config), (
                "validate_config() should have returned False since %r was not"
                "provided." % key)

    @patch("homeassistant.components.sensor.tcp.Sensor.update")
    def test_init_calls_update(self, mock_update):
        """
        Should call update() method during __init__().
        """
        tcp.Sensor(self.hass, TEST_CONFIG)
        assert mock_update.called

    @patch("socket.socket")
    @patch("select.select", return_value=(True, False, False))
    def test_update_connects_to_host_and_port(self, mock_select, mock_socket):
        """
        Should connect to the configured host and port.
        """
        tcp.Sensor(self.hass, TEST_CONFIG)
        mock_socket = mock_socket().__enter__()
        mock_socket.connect.assert_called_with((
            TEST_CONFIG[tcp.CONF_HOST],
            TEST_CONFIG[tcp.CONF_PORT]))

    @patch("socket.socket.connect", side_effect=socket.error())
    def test_update_returns_if_connecting_fails(self, mock_socket):
        """
        Should return if connecting to host fails.
        """
        with patch("homeassistant.components.sensor.tcp.Sensor.update"):
            sensor = tcp.Sensor(self.hass, TEST_CONFIG)
        assert sensor.update() is None

    @patch("socket.socket")
    @patch("select.select", return_value=(True, False, False))
    def test_update_sends_payload(self, mock_select, mock_socket):
        """
        Should send the configured payload as bytes.
        """
        tcp.Sensor(self.hass, TEST_CONFIG)
        mock_socket = mock_socket().__enter__()
        mock_socket.send.assert_called_with(
            TEST_CONFIG[tcp.CONF_PAYLOAD].encode()
        )

    @patch("socket.socket")
    @patch("select.select", return_value=(True, False, False))
    def test_update_calls_select_with_timeout(self, mock_select, mock_socket):
        """
        Should provide the timeout argument to select.
        """
        tcp.Sensor(self.hass, TEST_CONFIG)
        mock_socket = mock_socket().__enter__()
        mock_select.assert_called_with(
            [mock_socket], [], [], TEST_CONFIG[tcp.CONF_TIMEOUT])

    @patch("socket.socket")
    @patch("select.select", return_value=(True, False, False))
    def test_update_receives_packet_and_sets_as_state(
            self, mock_select, mock_socket):
        """
        Should receive the response from the socket and set it as the state.
        """
        test_value = "test_value"
        mock_socket = mock_socket().__enter__()
        mock_socket.recv.return_value = test_value.encode()
        config = copy(TEST_CONFIG)
        del config[tcp.CONF_VALUE_TEMPLATE]
        sensor = tcp.Sensor(self.hass, config)
        assert sensor._state == test_value

    @patch("socket.socket")
    @patch("select.select", return_value=(True, False, False))
    def test_update_renders_value_in_template(self, mock_select, mock_socket):
        """
        Should render the value in the provided template.
        """
        test_value = "test_value"
        mock_socket = mock_socket().__enter__()
        mock_socket.recv.return_value = test_value.encode()
        config = copy(TEST_CONFIG)
        config[tcp.CONF_VALUE_TEMPLATE] = "{{ value }} {{ 1+1 }}"
        sensor = tcp.Sensor(self.hass, config)
        assert sensor._state == "%s 2" % test_value
