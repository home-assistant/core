"""The tests for Radarr sensor platform."""
from datetime import datetime, timedelta

from homeassistant.components.radarr.sensor import SENSOR_TYPES
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from . import setup_integration

from tests.common import async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_sensors(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker):
    """Test for successfully setting up the Radarr platform."""
    for description in SENSOR_TYPES:
        description.entity_registry_enabled_default = True
    await setup_integration(hass, aioclient_mock)

    next_update = dt_util.utcnow() + timedelta(seconds=30)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.radarr_disk_space")
    assert state.state == "263.10"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "GB"
    assert state.attributes.get("D:\\") == "263.10/5216.31GB (5.04%)"
    assert len(state.attributes) == 4
    state = hass.states.get("sensor.radarr_upcoming")
    assert state.state == "1"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "Movies"
    assert state.attributes.get("string (2020)") == datetime(2021, 12, 3, 0, 0)
    state = hass.states.get("sensor.radarr_commands")
    assert state.state == "1"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "Commands"
    state = hass.states.get("sensor.radarr_status")
    assert state.state == "10.0.0.34882"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "Status"
    state = hass.states.get("sensor.radarr_movies")
    assert state.state == "1"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "Movies"
    assert state.attributes.get("string (0)") is True
