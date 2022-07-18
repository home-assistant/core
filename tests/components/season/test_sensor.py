"""The tests for the Season integration."""
from datetime import datetime

from freezegun import freeze_time
import pytest

from homeassistant.components.season.const import (
    DOMAIN,
    TYPE_ASTRONOMICAL,
    TYPE_METEOROLOGICAL,
)
from homeassistant.components.season.sensor import (
    STATE_AUTUMN,
    STATE_SPRING,
    STATE_SUMMER,
    STATE_WINTER,
)
from homeassistant.const import CONF_TYPE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry

HEMISPHERE_NORTHERN = {
    "homeassistant": {"latitude": 48.864716, "longitude": 2.349014},
    "sensor": {"platform": "season", "type": "astronomical"},
}

HEMISPHERE_SOUTHERN = {
    "homeassistant": {"latitude": -33.918861, "longitude": 18.423300},
    "sensor": {"platform": "season", "type": "astronomical"},
}

HEMISPHERE_EQUATOR = {
    "homeassistant": {"latitude": 0, "longitude": -51.065100},
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
async def test_season_northern_hemisphere(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    type: str,
    day: datetime,
    expected: str,
) -> None:
    """Test that season should be summer."""
    hass.config.latitude = HEMISPHERE_NORTHERN["homeassistant"]["latitude"]
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, unique_id=type, data={CONF_TYPE: type}
    )

    with freeze_time(day):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.season")
    assert state
    assert state.state == expected

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("sensor.season")
    assert entry
    assert entry.unique_id == mock_config_entry.entry_id


@pytest.mark.parametrize("type,day,expected", SOUTHERN_PARAMETERS, ids=idfn)
async def test_season_southern_hemisphere(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    type: str,
    day: datetime,
    expected: str,
) -> None:
    """Test that season should be summer."""
    hass.config.latitude = HEMISPHERE_SOUTHERN["homeassistant"]["latitude"]
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, unique_id=type, data={CONF_TYPE: type}
    )

    with freeze_time(day):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.season")
    assert state
    assert state.state == expected

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("sensor.season")
    assert entry
    assert entry.unique_id == mock_config_entry.entry_id

    device_registry = dr.async_get(hass)
    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.identifiers == {(DOMAIN, mock_config_entry.entry_id)}
    assert device_entry.name == "Season"
    assert device_entry.entry_type is dr.DeviceEntryType.SERVICE


async def test_season_equator(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that season should be unknown for equator."""
    hass.config.latitude = HEMISPHERE_EQUATOR["homeassistant"]["latitude"]
    mock_config_entry.add_to_hass(hass)

    with freeze_time(datetime(2017, 9, 3, 0, 0)):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.season")
    assert state
    assert state.state == STATE_UNKNOWN

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("sensor.season")
    assert entry
    assert entry.unique_id == mock_config_entry.entry_id
