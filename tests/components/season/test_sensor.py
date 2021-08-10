"""The tests for the Season sensor platform."""
from datetime import datetime
from unittest.mock import patch

import pytest

from homeassistant.components.season.sensor import (
    STATE_AUTUMN,
    STATE_SPRING,
    STATE_SUMMER,
    STATE_WINTER,
    TYPE_ASTRONOMICAL,
    TYPE_METEOROLOGICAL,
)
from homeassistant.const import STATE_UNKNOWN
from homeassistant.setup import async_setup_component

HEMISPHERE_NORTHERN = {
    "homeassistant": {"latitude": "48.864716", "longitude": "2.349014"},
    "sensor": {"platform": "season", "type": "astronomical"},
}

HEMISPHERE_SOUTHERN = {
    "homeassistant": {"latitude": "-33.918861", "longitude": "18.423300"},
    "sensor": {"platform": "season", "type": "astronomical"},
}

HEMISPHERE_EQUATOR = {
    "homeassistant": {"latitude": "0", "longitude": "-51.065100"},
    "sensor": {"platform": "season", "type": "astronomical"},
}

HEMISPHERE_EMPTY = {
    "homeassistant": {},
    "sensor": {"platform": "season", "type": "meteorological"},
}

NORTHERN_PARAMETERS = [
    (TYPE_ASTRONOMICAL, datetime(2017, 9, 3, 0, 0), STATE_SUMMER),
    (TYPE_METEOROLOGICAL, datetime(2017, 8, 13, 0, 0), STATE_SUMMER),
    (TYPE_ASTRONOMICAL, datetime(2017, 9, 23, 0, 0), STATE_AUTUMN),
    (TYPE_METEOROLOGICAL, datetime(2017, 9, 3, 0, 0), STATE_AUTUMN),
    (TYPE_ASTRONOMICAL, datetime(2017, 12, 25, 0, 0), STATE_WINTER),
    (TYPE_METEOROLOGICAL, datetime(2017, 12, 3, 0, 0), STATE_WINTER),
    (TYPE_ASTRONOMICAL, datetime(2017, 4, 1, 0, 0), STATE_SPRING),
    (TYPE_METEOROLOGICAL, datetime(2017, 3, 3, 0, 0), STATE_SPRING),
]

SOUTHERN_PARAMETERS = [
    (TYPE_ASTRONOMICAL, datetime(2017, 12, 25, 0, 0), STATE_SUMMER),
    (TYPE_METEOROLOGICAL, datetime(2017, 12, 3, 0, 0), STATE_SUMMER),
    (TYPE_ASTRONOMICAL, datetime(2017, 4, 1, 0, 0), STATE_AUTUMN),
    (TYPE_METEOROLOGICAL, datetime(2017, 3, 3, 0, 0), STATE_AUTUMN),
    (TYPE_ASTRONOMICAL, datetime(2017, 9, 3, 0, 0), STATE_WINTER),
    (TYPE_METEOROLOGICAL, datetime(2017, 8, 13, 0, 0), STATE_WINTER),
    (TYPE_ASTRONOMICAL, datetime(2017, 9, 23, 0, 0), STATE_SPRING),
    (TYPE_METEOROLOGICAL, datetime(2017, 9, 3, 0, 0), STATE_SPRING),
]


def idfn(val):
    """Provide IDs for pytest parametrize."""
    if isinstance(val, (datetime)):
        return val.strftime("%Y%m%d")


@pytest.mark.parametrize("type,day,expected", NORTHERN_PARAMETERS, ids=idfn)
async def test_season_northern_hemisphere(hass, type, day, expected):
    """Test that season should be summer."""
    hass.config.latitude = HEMISPHERE_NORTHERN["homeassistant"]["latitude"]

    config = {
        **HEMISPHERE_NORTHERN,
        "sensor": {"platform": "season", "type": type},
    }

    with patch("homeassistant.components.season.sensor.utcnow", return_value=day):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.season")
    assert state
    assert state.state == expected


@pytest.mark.parametrize("type,day,expected", SOUTHERN_PARAMETERS, ids=idfn)
async def test_season_southern_hemisphere(hass, type, day, expected):
    """Test that season should be summer."""
    hass.config.latitude = HEMISPHERE_SOUTHERN["homeassistant"]["latitude"]

    config = {
        **HEMISPHERE_SOUTHERN,
        "sensor": {"platform": "season", "type": type},
    }

    with patch("homeassistant.components.season.sensor.utcnow", return_value=day):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.season")
    assert state
    assert state.state == expected


async def test_season_equator(hass):
    """Test that season should be unknown for equator."""
    hass.config.latitude = HEMISPHERE_EQUATOR["homeassistant"]["latitude"]
    day = datetime(2017, 9, 3, 0, 0)

    with patch("homeassistant.components.season.sensor.utcnow", return_value=day):
        assert await async_setup_component(hass, "sensor", HEMISPHERE_EQUATOR)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.season")
    assert state
    assert state.state == STATE_UNKNOWN


async def test_setup_hemisphere_empty(hass):
    """Test platform setup of missing latlong."""
    hass.config.latitude = None
    assert await async_setup_component(hass, "sensor", HEMISPHERE_EMPTY)
    await hass.async_block_till_done()
    assert hass.config.as_dict()["latitude"] is None
