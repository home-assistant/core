"""Test configuration and mocks for TCP integration."""

from unittest.mock import patch

import pytest

from homeassistant.components.tcp import DOMAIN
import homeassistant.components.tcp.common as tcp
from homeassistant.util.dt import utcnow

socket_test_value = "value"

HOST_TEST_CONFIG = {
    tcp.CONF_HOST: "test_host",
    tcp.CONF_PORT: 12345,
    tcp.CONF_TIMEOUT: tcp.DEFAULT_TIMEOUT + 1,
    tcp.CONF_BUFFER_SIZE: tcp.DEFAULT_BUFFER_SIZE + 1,
}

SENSOR_TEST_CONFIG = {
    tcp.CONF_NAME: "test_name",
    tcp.CONF_PAYLOAD: "test_payload",
    tcp.CONF_VALUE_TEMPLATE: "{{ 'test_' + value }}",
    tcp.CONF_UNIT_OF_MEASUREMENT: "test_unit",
}

BINARY_SENSOR_TEST_CONFIG = {
    tcp.CONF_NAME: "test_name",
    tcp.CONF_PAYLOAD: "test_payload",
    tcp.CONF_VALUE_TEMPLATE: "{{ 'test_' + value }}",
    tcp.CONF_VALUE_ON: "test_on",
}

TEST_CONFIG_COMPONENTS = {
    "sensor": {"platform": "tcp", **HOST_TEST_CONFIG, **SENSOR_TEST_CONFIG},
    "binary_sensor": {
        "platform": "tcp",
        **HOST_TEST_CONFIG,
        **BINARY_SENSOR_TEST_CONFIG,
    },
}

TEST_CONFIG = {
    DOMAIN: [
        {
            **HOST_TEST_CONFIG,
            "sensors": [SENSOR_TEST_CONFIG],
            "binary_sensors": [BINARY_SENSOR_TEST_CONFIG],
        }
    ]
}


@pytest.fixture(name="mock_socket")
def mock_socket_fixture(mock_select):
    """Mock socket."""
    with patch("homeassistant.components.tcp.common.socket.socket") as mock_socket:
        socket_instance = mock_socket.return_value.__enter__.return_value
        socket_instance.recv.return_value = socket_test_value.encode()
        yield socket_instance


@pytest.fixture(name="mock_select")
def mock_select_fixture():
    """Mock select."""
    with patch(
        "homeassistant.components.tcp.common.select.select",
        return_value=(True, False, False),
    ) as mock_select:
        yield mock_select


@pytest.fixture(name="mock_ssl_context")
def mock_ssl_context_fixture():
    """Mock select."""
    with patch(
        "homeassistant.components.tcp.common.ssl.create_default_context",
    ) as mock_ssl_context:
        mock_ssl_context.return_value.wrap_socket.return_value.recv.return_value = (
            socket_test_value + "_ssl"
        ).encode()
        yield mock_ssl_context


@pytest.fixture
def now():
    """Return datetime UTC now."""
    return utcnow()
