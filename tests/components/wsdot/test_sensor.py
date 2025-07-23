"""The tests for the WSDOT platform."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

from homeassistant.components.wsdot.const import CONF_TRAVEL_TIMES, DOMAIN
from homeassistant.components.wsdot.sensor import SCAN_INTERVAL
from homeassistant.const import (
    CONF_API_KEY,
    CONF_ID,
    CONF_NAME,
    CONF_PLATFORM,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed


async def test_travel_sensor_details(
    hass: HomeAssistant,
    mock_travel_time: AsyncMock,
    sync_sensor,
) -> None:
    """Test the wsdot Travel Time sensor details."""
    state = hass.states.get("sensor.i90_eb")
    assert state is not None
    assert state.name == "I90 EB"
    assert state.state == "11"
    assert (
        state.attributes["Description"]
        == "Downtown Seattle to Downtown Bellevue via I-90"
    )
    assert state.attributes["TimeUpdated"] == datetime(
        2017, 1, 21, 15, 10, tzinfo=timezone(timedelta(hours=-8))
    )


async def test_travel_sensor_platform_setup(
    hass: HomeAssistant,
    mock_travel_time: AsyncMock,
) -> None:
    """Test the wsdot Travel Time sensor still supports setup from platform config."""
    assert await async_setup_component(
        hass,
        Platform.SENSOR,
        {
            Platform.SENSOR: [
                {
                    CONF_PLATFORM: DOMAIN,
                    CONF_API_KEY: "foo",
                    CONF_TRAVEL_TIMES: [{CONF_ID: 96, CONF_NAME: "I90 EB"}],
                }
            ]
        },
    )
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    state = hass.states.get("sensor.i90_eb")
    assert state is not None
    assert state.name == "I90 EB"
    assert (
        state.attributes["Description"]
        == "Downtown Seattle to Downtown Bellevue via I-90"
    )
    assert state.attributes["TimeUpdated"] == datetime(
        2017, 1, 21, 15, 10, tzinfo=timezone(timedelta(hours=-8))
    )
