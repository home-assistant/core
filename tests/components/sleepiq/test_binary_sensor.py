"""The tests for SleepIQ binary sensor platform."""
from unittest.mock import MagicMock

from homeassistant.components.sleepiq import binary_sensor as sleepiq
from homeassistant.setup import async_setup_component

from tests.components.sleepiq.test_init import mock_responses

CONFIG = {"username": "foo", "password": "bar"}


async def test_sensor_setup(hass, requests_mock):
    """Test for successfully setting up the SleepIQ platform."""
    mock_responses(requests_mock)

    await async_setup_component(hass, "sleepiq", {"sleepiq": CONFIG})

    device_mock = MagicMock()
    sleepiq.setup_platform(hass, CONFIG, device_mock, MagicMock())
    devices = device_mock.call_args[0][0]
    assert len(devices) == 2

    left_side = devices[1]
    assert left_side.name == "SleepNumber ILE Test1 Is In Bed"
    assert left_side.state == "on"

    right_side = devices[0]
    assert right_side.name == "SleepNumber ILE Test2 Is In Bed"
    assert right_side.state == "off"


async def test_setup_single(hass, requests_mock):
    """Test for successfully setting up the SleepIQ platform."""
    mock_responses(requests_mock, single=True)

    await async_setup_component(hass, "sleepiq", {"sleepiq": CONFIG})

    device_mock = MagicMock()
    sleepiq.setup_platform(hass, CONFIG, device_mock, MagicMock())
    devices = device_mock.call_args[0][0]
    assert len(devices) == 1

    right_side = devices[0]
    assert right_side.name == "SleepNumber ILE Test1 Is In Bed"
    assert right_side.state == "on"
