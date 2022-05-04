"""Test the Litter-Robot binary sensor entity."""
from unittest.mock import Mock

from homeassistant.components.binary_sensor import DOMAIN as PLATFORM_DOMAIN
from homeassistant.components.litterrobot.binary_sensor import (
    LitterRobotTimingModeSensor,
)

from .conftest import create_mock_robot, setup_integration

TIMING_MODE_ENTITY_ID = "binary_sensor.test_timing_mode"


async def test_timing_mode_binary_sensor(hass, mock_account):
    """Tests the waste drawer sensor entity was set up."""
    await setup_integration(hass, mock_account, PLATFORM_DOMAIN)

    sensor = hass.states.get(TIMING_MODE_ENTITY_ID)
    assert sensor
    assert sensor.is_on is False
    assert sensor.icon == "mdi:timer-off-outline"


async def test_sleep_time_sensor_in_true_state(hass):
    """Tests the sleep mode start time sensor where sleep mode is inactive."""
    robot = create_mock_robot({"unitStatus": "CST"})
    sensor = LitterRobotTimingModeSensor(robot, "Timing Mode", Mock())
    sensor.hass = hass

    assert sensor
    assert sensor.is_on is True
    assert sensor.icon == "mdi:timer-outline"
