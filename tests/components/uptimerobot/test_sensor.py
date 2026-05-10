"""Test UptimeRobot sensor."""

from unittest.mock import patch

from pyuptimerobot import UptimeRobotAuthenticationException

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.uptimerobot.const import COORDINATOR_UPDATE_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .common import (
    MOCK_UPTIMEROBOT_CONFIG_ENTRY_DATA,
    MOCK_UPTIMEROBOT_MONITOR,
    MOCK_UPTIMEROBOT_MONITOR_2,
    STATE_UP,
    UPTIMEROBOT_SENSOR_TEST_ENTITY,
    mock_uptimerobot_api_response,
    setup_uptimerobot_integration,
)

from tests.common import MockConfigEntry, async_fire_time_changed


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
        "started",
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
                MOCK_UPTIMEROBOT_MONITOR,
                MOCK_UPTIMEROBOT_MONITOR_2,
            ]
        ),
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + COORDINATOR_UPDATE_INTERVAL)
        await hass.async_block_till_done()

        assert (entity := hass.states.get(UPTIMEROBOT_SENSOR_TEST_ENTITY))
        assert entity.state == STATE_UP

        assert (entity := hass.states.get(entity_id_2))
        assert entity.state == STATE_UP


async def test_sensor_monitor_status_missing(
    hass: HomeAssistant,
) -> None:
    """Test sensor becomes unknown when the monitor status is missing."""
    monitor_without_status = {**MOCK_UPTIMEROBOT_MONITOR, "status": None}
    mock_entry = MockConfigEntry(**MOCK_UPTIMEROBOT_CONFIG_ENTRY_DATA)
    mock_entry.add_to_hass(hass)

    with patch(
        "pyuptimerobot.UptimeRobot.async_get_monitors",
        return_value=mock_uptimerobot_api_response(data=[monitor_without_status]),
    ):
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert (entity := hass.states.get(UPTIMEROBOT_SENSOR_TEST_ENTITY))
    assert entity.state == STATE_UNKNOWN
