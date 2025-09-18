"""Test UptimeRobot sensor."""

from unittest.mock import patch

from pyuptimerobot import UptimeRobotAuthenticationException

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.uptimerobot.const import COORDINATOR_UPDATE_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .common import (
    MOCK_UPTIMEROBOT_MONITOR,
    STATE_UP,
    UPTIMEROBOT_SENSOR_TEST_ENTITY,
    mock_uptimerobot_api_response,
    setup_uptimerobot_integration,
)

from tests.common import async_fire_time_changed


async def test_presentation(hass: HomeAssistant) -> None:
    """Test the presentation of UptimeRobot sensors."""
    await setup_uptimerobot_integration(hass)

    assert (entity := hass.states.get(UPTIMEROBOT_SENSOR_TEST_ENTITY)) is not None
    assert entity.state == STATE_UP
    assert entity.attributes["target"] == MOCK_UPTIMEROBOT_MONITOR["url"]
    assert entity.attributes["device_class"] == SensorDeviceClass.ENUM
    assert entity.attributes["options"] == [
        "down",
        "not_checked_yet",
        "pause",
        "seems_down",
        "up",
    ]


async def test_unavailable_on_update_failure(hass: HomeAssistant) -> None:
    """Test entity unavailable on update failure."""
    await setup_uptimerobot_integration(hass)

    assert (entity := hass.states.get(UPTIMEROBOT_SENSOR_TEST_ENTITY)) is not None
    assert entity.state == STATE_UP

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_monitors",
        side_effect=UptimeRobotAuthenticationException,
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + COORDINATOR_UPDATE_INTERVAL)
        await hass.async_block_till_done()

    assert (entity := hass.states.get(UPTIMEROBOT_SENSOR_TEST_ENTITY)) is not None
    assert entity.state == STATE_UNAVAILABLE


async def test_sensor_dynamic(hass: HomeAssistant) -> None:
    """Test sensor dynamically added."""
    await setup_uptimerobot_integration(hass)

    assert (entity := hass.states.get(UPTIMEROBOT_SENSOR_TEST_ENTITY))
    assert entity.state == STATE_UP

    entity_id_2 = "sensor.test_monitor_2"

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_monitors",
        return_value=mock_uptimerobot_api_response(
            data=[
                {
                    "id": 1234,
                    "friendly_name": "Test monitor",
                    "status": 2,
                    "type": 1,
                    "url": "http://example.com",
                },
                {
                    "id": 5678,
                    "friendly_name": "Test monitor 2",
                    "status": 2,
                    "type": 1,
                    "url": "http://example2.com",
                },
            ]
        ),
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + COORDINATOR_UPDATE_INTERVAL)
        await hass.async_block_till_done()

        assert (entity := hass.states.get(UPTIMEROBOT_SENSOR_TEST_ENTITY))
        assert entity.state == STATE_UP

        assert (entity := hass.states.get(entity_id_2))
        assert entity.state == STATE_UP
