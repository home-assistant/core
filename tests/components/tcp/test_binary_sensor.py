"""The tests for the TCP binary sensor platform."""
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.tcp import binary_sensor as bin_tcp
import homeassistant.components.tcp.sensor as tcp
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component
import tests.components.tcp.test_sensor as test_tcp


@pytest.fixture
def mock_update():
    """Pytest fixture for tcp sensor update."""
    with patch("homeassistant.components.tcp.sensor.TcpSensor.update") as mock_update:
        yield mock_update.return_value


async def test_setup_platform_valid_config(hass):
    """Check a valid configuration."""
    with assert_setup_component(0, "binary_sensor"):
        assert await async_setup_component(hass, "binary_sensor", test_tcp.TEST_CONFIG)


async def test_setup_platform_invalid_config(hass):
    """Check the invalid configuration."""
    with assert_setup_component(0):
        assert await async_setup_component(
            hass,
            "binary_sensor",
            {"binary_sensor": {"platform": "tcp", "porrt": 1234}},
        )


def test_setup_platform_devices(mock_update):
    """Check the supplied config and call add_entities with sensor."""
    add_entities = Mock()
    ret = bin_tcp.setup_platform(None, test_tcp.TEST_CONFIG, add_entities)
    assert ret is None
    assert add_entities.called
    assert isinstance(add_entities.call_args[0][0][0], bin_tcp.TcpBinarySensor)


def test_is_on_true(hass, mock_update):
    """Check the return that _state is value_on."""
    sensor = bin_tcp.TcpBinarySensor(hass, test_tcp.TEST_CONFIG["sensor"])
    sensor._state = test_tcp.TEST_CONFIG["sensor"][tcp.CONF_VALUE_ON]
    print(sensor._state)
    assert sensor.is_on


def test_is_on_false(hass, mock_update):
    """Check the return that _state is not the same as value_on."""
    sensor = bin_tcp.TcpBinarySensor(hass, test_tcp.TEST_CONFIG["sensor"])
    sensor._state = "{} abc".format(test_tcp.TEST_CONFIG["sensor"][tcp.CONF_VALUE_ON])
    assert not sensor.is_on
