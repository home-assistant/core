"""The test for the zodiac sensor platform."""
from datetime import datetime
from unittest.mock import patch

import pytest

from homeassistant.components.sensor import ATTR_OPTIONS, SensorDeviceClass
from homeassistant.components.zodiac.const import (
    ATTR_ELEMENT,
    ATTR_MODALITY,
    DOMAIN,
    ELEMENT_EARTH,
    ELEMENT_FIRE,
    ELEMENT_WATER,
    MODALITY_CARDINAL,
    MODALITY_FIXED,
    SIGN_ARIES,
    SIGN_SCORPIO,
    SIGN_TAURUS,
)
from homeassistant.const import ATTR_DEVICE_CLASS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

DAY1 = datetime(2020, 11, 15, tzinfo=dt_util.UTC)
DAY2 = datetime(2020, 4, 20, tzinfo=dt_util.UTC)
DAY3 = datetime(2020, 4, 21, tzinfo=dt_util.UTC)


@pytest.mark.parametrize(
    ("now", "sign", "element", "modality"),
    [
        (DAY1, SIGN_SCORPIO, ELEMENT_WATER, MODALITY_FIXED),
        (DAY2, SIGN_ARIES, ELEMENT_FIRE, MODALITY_CARDINAL),
        (DAY3, SIGN_TAURUS, ELEMENT_EARTH, MODALITY_FIXED),
    ],
)
async def test_zodiac_day(hass: HomeAssistant, now, sign, element, modality) -> None:
    """Test the zodiac sensor."""
    hass.config.set_time_zone("UTC")
    config = {DOMAIN: {}}

    with patch("homeassistant.components.zodiac.sensor.utcnow", return_value=now):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.zodiac")
    assert state
    assert state.state == sign
    assert state.attributes
    assert state.attributes[ATTR_ELEMENT] == element
    assert state.attributes[ATTR_MODALITY] == modality
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENUM
    assert state.attributes[ATTR_OPTIONS] == [
        "aquarius",
        "aries",
        "cancer",
        "capricorn",
        "gemini",
        "leo",
        "libra",
        "pisces",
        "sagittarius",
        "scorpio",
        "taurus",
        "virgo",
    ]

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("sensor.zodiac")
    assert entry
    assert entry.unique_id == "zodiac"
    assert entry.translation_key == "sign"
