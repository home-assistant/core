"""Test the Litter-Robot sensor entity."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.litterrobot.sensor import icon_for_gauge_level
from homeassistant.components.sensor import DOMAIN as PLATFORM_DOMAIN, SensorDeviceClass
from homeassistant.const import PERCENTAGE, STATE_UNKNOWN, UnitOfMass
from homeassistant.core import HomeAssistant

from .conftest import setup_integration

WASTE_DRAWER_ENTITY_ID = "sensor.test_waste_drawer"
SLEEP_END_TIME_ENTITY_ID = "sensor.test_sleep_mode_end_time"
SLEEP_START_TIME_ENTITY_ID = "sensor.test_sleep_mode_start_time"


async def test_waste_drawer_sensor(
    hass: HomeAssistant, mock_account: MagicMock
) -> None:
    """Tests the waste drawer sensor entity was set up."""
    await setup_integration(hass, mock_account, PLATFORM_DOMAIN)

    sensor = hass.states.get(WASTE_DRAWER_ENTITY_ID)
    assert sensor
    assert sensor.state == "50.0"
    assert sensor.attributes["unit_of_measurement"] == PERCENTAGE


async def test_sleep_time_sensor_with_sleep_disabled(
    hass: HomeAssistant, mock_account_with_sleep_disabled_robot: MagicMock
) -> None:
    """Tests the sleep mode start time sensor where sleep mode is disabled."""
    await setup_integration(
        hass, mock_account_with_sleep_disabled_robot, PLATFORM_DOMAIN
    )

    sensor = hass.states.get(SLEEP_START_TIME_ENTITY_ID)
    assert sensor
    assert sensor.state == STATE_UNKNOWN
    assert sensor.attributes["device_class"] == SensorDeviceClass.TIMESTAMP

    sensor = hass.states.get(SLEEP_END_TIME_ENTITY_ID)
    assert sensor.state == STATE_UNKNOWN
    assert sensor.attributes["device_class"] == SensorDeviceClass.TIMESTAMP


async def test_gauge_icon() -> None:
    """Test icon generator for gauge sensor."""

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


@pytest.mark.freeze_time("2022-09-18 23:00:44+00:00")
async def test_litter_robot_sensor(
    hass: HomeAssistant, mock_account_with_litterrobot_4: MagicMock
) -> None:
    """Tests Litter-Robot sensors."""
    await setup_integration(hass, mock_account_with_litterrobot_4, PLATFORM_DOMAIN)

    sensor = hass.states.get(SLEEP_START_TIME_ENTITY_ID)
    assert sensor.state == "2022-09-19T04:00:00+00:00"
    assert sensor.attributes["device_class"] == SensorDeviceClass.TIMESTAMP
    sensor = hass.states.get(SLEEP_END_TIME_ENTITY_ID)
    assert sensor.state == "2022-09-16T07:00:00+00:00"
    assert sensor.attributes["device_class"] == SensorDeviceClass.TIMESTAMP
    sensor = hass.states.get("sensor.test_last_seen")
    assert sensor.state == "2022-09-17T12:06:37+00:00"
    assert sensor.attributes["device_class"] == SensorDeviceClass.TIMESTAMP
    sensor = hass.states.get("sensor.test_status_code")
    assert sensor.state == "rdy"
    assert sensor.attributes["device_class"] == SensorDeviceClass.ENUM
    sensor = hass.states.get("sensor.test_litter_level")
    assert sensor.state == "70.0"
    assert sensor.attributes["unit_of_measurement"] == PERCENTAGE
    sensor = hass.states.get("sensor.test_pet_weight")
    assert sensor.state == "12.0"
    assert sensor.attributes["unit_of_measurement"] == UnitOfMass.POUNDS


async def test_feeder_robot_sensor(
    hass: HomeAssistant, mock_account_with_feederrobot: MagicMock
) -> None:
    """Tests Feeder-Robot sensors."""
    await setup_integration(hass, mock_account_with_feederrobot, PLATFORM_DOMAIN)
    sensor = hass.states.get("sensor.test_food_level")
    assert sensor.state == "10"
    assert sensor.attributes["unit_of_measurement"] == PERCENTAGE
