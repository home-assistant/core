"""Test the Litter-Robot sensor entity."""
from unittest.mock import Mock

from homeassistant.components.litterrobot.sensor import LitterRobotSleepTimeSensor
from homeassistant.components.sensor import DOMAIN as PLATFORM_DOMAIN
from homeassistant.const import DEVICE_CLASS_TIMESTAMP, PERCENTAGE

from .conftest import create_mock_robot, setup_integration

WASTE_DRAWER_ENTITY_ID = "sensor.test_waste_drawer"


async def test_waste_drawer_sensor(hass, mock_account):
    """Tests the waste drawer sensor entity was set up."""
    await setup_integration(hass, mock_account, PLATFORM_DOMAIN)

    sensor = hass.states.get(WASTE_DRAWER_ENTITY_ID)
    assert sensor
    assert sensor.state == "50.0"
    assert sensor.attributes["unit_of_measurement"] == PERCENTAGE


async def test_sleep_time_sensor_with_none_state(hass):
    """Tests the sleep mode start time sensor where sleep mode is inactive."""
    robot = create_mock_robot({"sleepModeActive": "0"})
    sensor = LitterRobotSleepTimeSensor(
        robot, "Sleep Mode Start Time", Mock(), "sleep_mode_start_time"
    )

    assert sensor
    assert sensor.state is None
    assert sensor.device_class == DEVICE_CLASS_TIMESTAMP


async def test_gauge_icon():
    """Test icon generator for gauge sensor."""
    from homeassistant.components.litterrobot.sensor import icon_for_gauge_level

    GAUGE_EMPTY = "mdi:gauge-empty"
    GAUGE_LOW = "mdi:gauge-low"
    GAUGE = "mdi:gauge"
    GAUGE_FULL = "mdi:gauge-full"

    assert icon_for_gauge_level(None) == GAUGE_EMPTY
    assert icon_for_gauge_level(0) == GAUGE_EMPTY
    assert icon_for_gauge_level(5) == GAUGE_LOW
    assert icon_for_gauge_level(40) == GAUGE
    assert icon_for_gauge_level(80) == GAUGE_FULL
    assert icon_for_gauge_level(100) == GAUGE_FULL

    assert icon_for_gauge_level(None, 10) == GAUGE_EMPTY
    assert icon_for_gauge_level(0, 10) == GAUGE_EMPTY
    assert icon_for_gauge_level(5, 10) == GAUGE_EMPTY
    assert icon_for_gauge_level(40, 10) == GAUGE_LOW
    assert icon_for_gauge_level(80, 10) == GAUGE
    assert icon_for_gauge_level(100, 10) == GAUGE_FULL
