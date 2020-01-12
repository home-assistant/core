"""The tests for the TCP sensor platform."""
from copy import copy
import socket
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

import homeassistant.components.tcp.sensor as tcp
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.template import Template
from homeassistant.setup import setup_component

from tests.common import assert_setup_component, get_test_home_assistant

TEST_CONFIG = {
    "sensor": {
        "platform": "tcp",
        tcp.CONF_NAME: "test_name",
        tcp.CONF_HOST: "test_host",
        tcp.CONF_PORT: 12345,
        tcp.CONF_TIMEOUT: tcp.DEFAULT_TIMEOUT + 1,
        tcp.CONF_PAYLOAD: "test_payload",
        tcp.CONF_UNIT_OF_MEASUREMENT: "test_unit",
        tcp.CONF_VALUE_TEMPLATE: Template("test_template"),
        tcp.CONF_VALUE_ON: "test_on",
        tcp.CONF_BUFFER_SIZE: tcp.DEFAULT_BUFFER_SIZE + 1,
    }
}

KEYS_AND_DEFAULTS = {
    tcp.CONF_TIMEOUT: tcp.DEFAULT_TIMEOUT,
    tcp.CONF_UNIT_OF_MEASUREMENT: None,
    tcp.CONF_VALUE_TEMPLATE: None,
    tcp.CONF_VALUE_ON: None,
    tcp.CONF_BUFFER_SIZE: tcp.DEFAULT_BUFFER_SIZE,
}


class TestTCPSensor(unittest.TestCase):
    """Test the TCP Sensor."""

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    @patch("homeassistant.components.tcp.sensor.TcpSensor.update")
    def test_setup_platform_valid_config(self, mock_update):
        """Check a valid configuration and call add_entities with sensor."""
        with assert_setup_component(0, "sensor"):
            assert setup_component(self.hass, "sensor", TEST_CONFIG)

        add_entities = Mock()
        tcp.setup_platform(None, TEST_CONFIG["sensor"], add_entities)
        assert add_entities.called
        assert isinstance(add_entities.call_args[0][0][0], tcp.TcpSensor)

    def test_setup_platform_invalid_config(self):
        """Check an invalid configuration."""
        with assert_setup_component(0):
            assert setup_component(
                self.hass, "sensor", {"sensor": {"platform": "tcp", "porrt": 1234}}
            )

    @patch("homeassistant.components.tcp.sensor.TcpSensor.update")
    def test_name(self, mock_update):
        """Return the name if set in the configuration."""
        sensor = tcp.TcpSensor(self.hass, TEST_CONFIG["sensor"])
        assert sensor.name == TEST_CONFIG["sensor"][tcp.CONF_NAME]

    @patch("homeassistant.components.tcp.sensor.TcpSensor.update")
    def test_name_not_set(self, mock_update):
        """Return the superclass name property if not set in configuration."""
        config = copy(TEST_CONFIG["sensor"])
        del config[tcp.CONF_NAME]
        entity = Entity()
        sensor = tcp.TcpSensor(self.hass, config)
        assert sensor.name == entity.name

    @patch("homeassistant.components.tcp.sensor.TcpSensor.update")
    def test_state(self, mock_update):
        """Return the contents of _state."""
        sensor = tcp.TcpSensor(self.hass, TEST_CONFIG["sensor"])
        uuid = str(uuid4())
        sensor._state = uuid
        assert sensor.state == uuid

    @patch("homeassistant.components.tcp.sensor.TcpSensor.update")
    def test_unit_of_measurement(self, mock_update):
        """Return the configured unit of measurement."""
        sensor = tcp.TcpSensor(self.hass, TEST_CONFIG["sensor"])
        assert (
            sensor.unit_of_measurement
            == TEST_CONFIG["sensor"][tcp.CONF_UNIT_OF_MEASUREMENT]
        )

    @patch("homeassistant.components.tcp.sensor.TcpSensor.update")
    def test_config_valid_keys(self, *args):
        """Store valid keys in _config."""
        sensor = tcp.TcpSensor(self.hass, TEST_CONFIG["sensor"])
        del TEST_CONFIG["sensor"]["platform"]

        for key in TEST_CONFIG["sensor"]:
            assert key in sensor._config

    def test_validate_config_valid_keys(self):
        """Return True when provided with the correct keys."""
        with assert_setup_component(0, "sensor"):
            assert setup_component(self.hass, "sensor", TEST_CONFIG)

    @patch("homeassistant.components.tcp.sensor.TcpSensor.update")
    def test_config_invalid_keys(self, mock_update):
        """Shouldn't store invalid keys in _config."""
        config = copy(TEST_CONFIG["sensor"])
        config.update({"a": "test_a", "b": "test_b", "c": "test_c"})
        sensor = tcp.TcpSensor(self.hass, config)
        for invalid_key in "abc":
            assert invalid_key not in sensor._config

    def test_validate_config_invalid_keys(self):
        """Test with invalid keys plus some extra."""
        config = copy(TEST_CONFIG["sensor"])
        config.update({"a": "test_a", "b": "test_b", "c": "test_c"})
        with assert_setup_component(0, "sensor"):
            assert setup_component(self.hass, "sensor", {"tcp": config})

    @patch("homeassistant.components.tcp.sensor.TcpSensor.update")
    def test_config_uses_defaults(self, mock_update):
        """Check if defaults were set."""
        config = copy(TEST_CONFIG["sensor"])

        for key in KEYS_AND_DEFAULTS:
            del config[key]

        with assert_setup_component(1) as result_config:
            assert setup_component(self.hass, "sensor", {"sensor": config})

        sensor = tcp.TcpSensor(self.hass, result_config["sensor"][0])

        for key, default in KEYS_AND_DEFAULTS.items():
            assert sensor._config[key] == default

    def test_validate_config_missing_defaults(self):
        """Return True when defaulted keys are not provided."""
        config = copy(TEST_CONFIG["sensor"])

        for key in KEYS_AND_DEFAULTS:
            del config[key]

        with assert_setup_component(0, "sensor"):
            assert setup_component(self.hass, "sensor", {"tcp": config})

    def test_validate_config_missing_required(self):
        """Return False when required config items are missing."""
        for key in TEST_CONFIG["sensor"]:
            if key in KEYS_AND_DEFAULTS:
                continue
            config = copy(TEST_CONFIG["sensor"])
            del config[key]
            with assert_setup_component(0, "sensor"):
                assert setup_component(self.hass, "sensor", {"tcp": config})

    @patch("homeassistant.components.tcp.sensor.TcpSensor.update")
    def test_init_calls_update(self, mock_update):
        """Call update() method during __init__()."""
        tcp.TcpSensor(self.hass, TEST_CONFIG)
        assert mock_update.called

    @patch("socket.socket")
    @patch("select.select", return_value=(True, False, False))
    def test_update_connects_to_host_and_port(self, mock_select, mock_socket):
        """Connect to the configured host and port."""
        tcp.TcpSensor(self.hass, TEST_CONFIG["sensor"])
        mock_socket = mock_socket().__enter__()
        assert mock_socket.connect.mock_calls[0][1] == (
            (
                TEST_CONFIG["sensor"][tcp.CONF_HOST],
                TEST_CONFIG["sensor"][tcp.CONF_PORT],
            ),
        )

    @patch("socket.socket.connect", side_effect=socket.error())
    def test_update_returns_if_connecting_fails(self, *args):
        """Return if connecting to host fails."""
        with patch("homeassistant.components.tcp.sensor.TcpSensor.update"):
            sensor = tcp.TcpSensor(self.hass, TEST_CONFIG["sensor"])
        assert sensor.update() is None

    @patch("socket.socket.connect")
    @patch("socket.socket.send", side_effect=socket.error())
    def test_update_returns_if_sending_fails(self, *args):
        """Return if sending fails."""
        with patch("homeassistant.components.tcp.sensor.TcpSensor.update"):
            sensor = tcp.TcpSensor(self.hass, TEST_CONFIG["sensor"])
        assert sensor.update() is None

    @patch("socket.socket.connect")
    @patch("socket.socket.send")
    @patch("select.select", return_value=(False, False, False))
    def test_update_returns_if_select_fails(self, *args):
        """Return if select fails to return a socket."""
        with patch("homeassistant.components.tcp.sensor.TcpSensor.update"):
            sensor = tcp.TcpSensor(self.hass, TEST_CONFIG["sensor"])
        assert sensor.update() is None

    @patch("socket.socket")
    @patch("select.select", return_value=(True, False, False))
    def test_update_sends_payload(self, mock_select, mock_socket):
        """Send the configured payload as bytes."""
        tcp.TcpSensor(self.hass, TEST_CONFIG["sensor"])
        mock_socket = mock_socket().__enter__()
        mock_socket.send.assert_called_with(
            TEST_CONFIG["sensor"][tcp.CONF_PAYLOAD].encode()
        )

    @patch("socket.socket")
    @patch("select.select", return_value=(True, False, False))
    def test_update_calls_select_with_timeout(self, mock_select, mock_socket):
        """Provide the timeout argument to select."""
        tcp.TcpSensor(self.hass, TEST_CONFIG["sensor"])
        mock_socket = mock_socket().__enter__()
        mock_select.assert_called_with(
            [mock_socket], [], [], TEST_CONFIG["sensor"][tcp.CONF_TIMEOUT]
        )

    @patch("socket.socket")
    @patch("select.select", return_value=(True, False, False))
    def test_update_receives_packet_and_sets_as_state(self, mock_select, mock_socket):
        """Test the response from the socket and set it as the state."""
        test_value = "test_value"
        mock_socket = mock_socket().__enter__()
        mock_socket.recv.return_value = test_value.encode()
        config = copy(TEST_CONFIG["sensor"])
        del config[tcp.CONF_VALUE_TEMPLATE]
        sensor = tcp.TcpSensor(self.hass, config)
        assert sensor._state == test_value

    @patch("socket.socket")
    @patch("select.select", return_value=(True, False, False))
    def test_update_renders_value_in_template(self, mock_select, mock_socket):
        """Render the value in the provided template."""
        test_value = "test_value"
        mock_socket = mock_socket().__enter__()
        mock_socket.recv.return_value = test_value.encode()
        config = copy(TEST_CONFIG["sensor"])
        config[tcp.CONF_VALUE_TEMPLATE] = Template("{{ value }} {{ 1+1 }}")
        sensor = tcp.TcpSensor(self.hass, config)
        assert sensor._state == "%s 2" % test_value

    @patch("socket.socket")
    @patch("select.select", return_value=(True, False, False))
    def test_update_returns_if_template_render_fails(self, mock_select, mock_socket):
        """Return None if rendering the template fails."""
        test_value = "test_value"
        mock_socket = mock_socket().__enter__()
        mock_socket.recv.return_value = test_value.encode()
        config = copy(TEST_CONFIG["sensor"])
        config[tcp.CONF_VALUE_TEMPLATE] = Template("{{ this won't work")
        sensor = tcp.TcpSensor(self.hass, config)
        assert sensor.update() is None
