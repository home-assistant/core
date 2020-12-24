"""The test for the moon sensor platform."""
from datetime import datetime

from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.async_mock import patch

DAY1 = datetime(2017, 1, 1, 1, tzinfo=dt_util.UTC)
DAY2 = datetime(2017, 1, 18, 1, tzinfo=dt_util.UTC)


async def test_moon_day1(hass):
    """Test the Moon sensor."""
    config = {"sensor": {"platform": "moon", "name": "moon_day1"}}

    await async_setup_component(hass, HA_DOMAIN, {})
    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.moon_day1")

    with patch(
        "homeassistant.components.moon.sensor.dt_util.utcnow", return_value=DAY1
    ):
        await async_update_entity(hass, "sensor.moon_day1")

    assert hass.states.get("sensor.moon_day1").state == "waxing_crescent"


async def test_moon_day2(hass):
    """Test the Moon sensor."""
    config = {"sensor": {"platform": "moon", "name": "moon_day2"}}

    await async_setup_component(hass, HA_DOMAIN, {})
    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.moon_day2")

    with patch(
        "homeassistant.components.moon.sensor.dt_util.utcnow", return_value=DAY2
    ):
        await async_update_entity(hass, "sensor.moon_day2")

    assert hass.states.get("sensor.moon_day2").state == "waning_gibbous"


async def async_update_entity(hass, entity_id):
    """Run an update action for an entity."""
    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()
