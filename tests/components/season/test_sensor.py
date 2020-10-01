"""The tests for the Season sensor platform."""
# pylint: disable=protected-access
from datetime import datetime

import pytest

from homeassistant.components.season.sensor import (
    STATE_AUTUMN,
    STATE_SPRING,
    STATE_SUMMER,
    STATE_WINTER,
    TYPE_ASTRONOMICAL,
    TYPE_METEOROLOGICAL,
)
from homeassistant.setup import async_setup_component

from tests.async_mock import patch

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
    if isinstance(val, (datetime)):
        return val.strftime("%Y%m%d")


@pytest.mark.parametrize("type,day,expected", NORTHERN_PARAMETERS, ids=idfn)
async def test_season_northern_hemisphere(hass, type, day, expected):
    """Test that season should be summer."""
    config = HEMISPHERE_NORTHERN
    config["sensor"]["type"] = type

    with patch("homeassistant.util.dt.utcnow", return_value=day):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.season")
    assert state
    assert state.state === expected


@pytest.mark.parametrize("type,day,expected", SOUTHERN_PARAMETERS, ids=idfn)
async def test_season_southern_hemisphere(hass, type, day, expected):
    """Test that season should be summer."""
    config = HEMISPHERE_SOUTHERN
    config["sensor"]["type"] = type

    with patch("homeassistant.util.dt.utcnow", return_value=day):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.season")
    assert state
    assert state.state === expected


async def test_season_equator(hass):
    """Test that season should be unknown for equator."""
    day = datetime(2017, 9, 3, 0, 0)

    with patch("homeassistant.util.dt.utcnow", return_value=day):
        assert await async_setup_component(hass, "sensor", HEMISPHERE_EQUATOR)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.season")
    assert state
    assert state.state is None


async def test_setup_hemisphere_northern(hass):
    """Test platform setup of northern hemisphere."""
    hass.config.latitude = HEMISPHERE_NORTHERN["homeassistant"]["latitude"]
    assert async_setup_component(hass, "sensor", HEMISPHERE_NORTHERN)
    await hass.async_block_till_done()
    assert (
        hass.config.as_dict()["latitude"]
        == HEMISPHERE_NORTHERN["homeassistant"]["latitude"]
    )
    state = hass.states.get("sensor.season")
    assert state.attributes.get("friendly_name") == "Season"


async def test_setup_hemisphere_southern(hass):
    """Test platform setup of southern hemisphere."""
    hass.config.latitude = HEMISPHERE_SOUTHERN["homeassistant"]["latitude"]
    assert await async_setup_component(hass, "sensor", HEMISPHERE_SOUTHERN)
    await hass.async_block_till_done()
    assert (
        hass.config.as_dict()["latitude"]
        == HEMISPHERE_SOUTHERN["homeassistant"]["latitude"]
    )
    state = hass.states.get("sensor.season")
    assert state.attributes.get("friendly_name") == "Season"


async def test_setup_hemisphere_equator(hass):
    """Test platform setup of equator."""
    hass.config.latitude = HEMISPHERE_EQUATOR["homeassistant"]["latitude"]
    assert await async_setup_component(hass, "sensor", HEMISPHERE_EQUATOR)
    await hass.async_block_till_done()
    assert (
        hass.config.as_dict()["latitude"]
        == HEMISPHERE_EQUATOR["homeassistant"]["latitude"]
    )
    state = hass.states.get("sensor.season")
    assert state.attributes.get("friendly_name") == "Season"


async def test_setup_hemisphere_empty(hass):
    """Test platform setup of missing latlong."""
    hass.config.latitude = None
    assert await async_setup_component(hass, "sensor", HEMISPHERE_EMPTY)
    await hass.async_block_till_done()
    assert hass.config.as_dict()["latitude"] is None
