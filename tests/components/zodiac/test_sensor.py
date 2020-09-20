"""The test for the zodiac sensor platform."""
from datetime import datetime
import pytest

from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.zodiac import DOMAIN
from homeassistant.components.zodiac.sensor import (
    ATTR_ELEMENT,
    ATTR_MODALITY,
    ATTR_SIGN,
    ELEMENT_EARTH,
    ELEMENT_FIRE,
    ELEMENT_WATER,
    MODALITY_CARDINAL,
    MODALITY_FIXED,
    SIGN_ARIES,
    SIGN_SCORPIO,
    SIGN_TAURUS,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.async_mock import patch

DAY1 = datetime(2020, 11, 15, tzinfo=dt_util.UTC)
DAY2 = datetime(2020, 4, 20, tzinfo=dt_util.UTC)
DAY3 = datetime(2020, 4, 21, tzinfo=dt_util.UTC)


@pytest.mark.parametrize(
    "now,sign,element,modality",
    [
        (DAY1, SIGN_SCORPIO, ELEMENT_WATER, MODALITY_FIXED),
        (DAY2, SIGN_ARIES, ELEMENT_FIRE, MODALITY_CARDINAL),
        (DAY3, SIGN_TAURUS, ELEMENT_EARTH, MODALITY_FIXED),
    ],
)
async def test_zodiac_day(hass, now, sign, element, modality):
    """Test the zodiac sensor."""
    config = {SENSOR_DOMAIN: {"platform": DOMAIN}}

    await async_setup_component(hass, HA_DOMAIN, {})
    with patch(
        "homeassistant.components.zodiac.sensor.dt_util.utcnow", return_value=now
    ):
        assert await async_setup_component(hass, SENSOR_DOMAIN, config)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.zodiac")


    assert hass.states.get("sensor.zodiac").state == sign
    data = hass.states.get("sensor.zodiac").attributes
    assert data.get(ATTR_SIGN) == sign
    assert data.get(ATTR_ELEMENT) == element
    assert data.get(ATTR_MODALITY) == modality


async def test_zodiac_day2(hass):
    """Test the zodiac sensor."""
    config = {"sensor": {"platform": "zodiac"}}

    await async_setup_component(hass, HA_DOMAIN, {})
    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.zodiac")

    with patch(
        "homeassistant.components.zodiac.sensor.dt_util.utcnow", return_value=DAY2
    ):
        await async_update_entity(hass, "sensor.zodiac")

    assert hass.states.get("sensor.zodiac").state == SIGN_ARIES
    data = hass.states.get("sensor.zodiac").attributes
    assert data.get(ATTR_SIGN) == SIGN_ARIES
    assert data.get(ATTR_ELEMENT) == ELEMENT_FIRE
    assert data.get(ATTR_MODALITY) == MODALITY_CARDINAL


async def test_zodiac_day3(hass):
    """Test the zodiac sensor."""
    config = {"sensor": {"platform": "zodiac"}}

    await async_setup_component(hass, HA_DOMAIN, {})
    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.zodiac")

    with patch(
        "homeassistant.components.zodiac.sensor.dt_util.utcnow", return_value=DAY3
    ):
        await async_update_entity(hass, "sensor.zodiac")

    assert hass.states.get("sensor.zodiac").state == SIGN_TAURUS
    data = hass.states.get("sensor.zodiac").attributes
    assert data.get(ATTR_SIGN) == SIGN_TAURUS
    assert data.get(ATTR_ELEMENT) == ELEMENT_EARTH
    assert data.get(ATTR_MODALITY) == MODALITY_FIXED


async def async_update_entity(hass, entity_id):
    """Run an update action for an entity."""
    await hass.services.async_call(
        HA_DOMAIN, SERVICE_UPDATE_ENTITY, {ATTR_ENTITY_ID: entity_id}, blocking=True,
    )
    await hass.async_block_till_done()
