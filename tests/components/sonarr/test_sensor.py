"""Tests for the Sonarr sensor platform."""
from datetime import timedelta
from unittest.mock import MagicMock

from aiopyarr import ArrException
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    UnitOfInformation,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed

UPCOMING_ENTITY_ID = f"{SENSOR_DOMAIN}.sonarr_upcoming"


async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sonarr: MagicMock,
    entity_registry_enabled_by_default: None,
) -> None:
    """Test the creation and values of the sensors."""
    registry = er.async_get(hass)

    sensors = {
        "commands": "sonarr_commands",
        "diskspace": "sonarr_disk_space",
        "queue": "sonarr_queue",
        "series": "sonarr_shows",
        "wanted": "sonarr_wanted",
    }

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    for unique, oid in sensors.items():
        entity = registry.async_get(f"sensor.{oid}")
        assert entity
        assert entity.unique_id == f"{mock_config_entry.entry_id}_{unique}"

    state = hass.states.get("sensor.sonarr_commands")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:code-braces"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "Commands"
    assert state.state == "2"

    state = hass.states.get("sensor.sonarr_disk_space")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:harddisk"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfInformation.GIGABYTES
    assert state.attributes.get("C:\\") == "263.10/465.42GB (56.53%)"
    assert state.state == "263.10"

    state = hass.states.get("sensor.sonarr_queue")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:download"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "Episodes"
    assert state.attributes.get("The Andy Griffith Show S01E01") == "100.00%"
    assert state.state == "1"

    state = hass.states.get("sensor.sonarr_shows")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:television"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "Series"
    assert state.attributes.get("The Andy Griffith Show") == "0/0 Episodes"
    assert state.state == "1"

    state = hass.states.get("sensor.sonarr_upcoming")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:television"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "Episodes"
    assert state.attributes.get("Bob's Burgers") == "S04E11"
    assert state.state == "1"

    state = hass.states.get("sensor.sonarr_wanted")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:television"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "Episodes"
    assert state.attributes.get("Bob's Burgers S04E11") == "2014-01-26T17:30:00-08:00"
    assert (
        state.attributes.get("The Andy Griffith Show S01E01")
        == "1960-10-02T17:00:00-08:00"
    )
    assert state.state == "2"


@pytest.mark.parametrize(
    "entity_id",
    (
        "sensor.sonarr_commands",
        "sensor.sonarr_disk_space",
        "sensor.sonarr_queue",
        "sensor.sonarr_shows",
        "sensor.sonarr_wanted",
    ),
)
async def test_disabled_by_default_sensors(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_id: str,
) -> None:
    """Test the disabled by default sensors."""
    registry = er.async_get(hass)

    state = hass.states.get(entity_id)
    assert state is None

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_availability(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_sonarr: MagicMock,
) -> None:
    """Test entity availability."""
    now = dt_util.utcnow()

    mock_config_entry.add_to_hass(hass)
    freezer.move_to(now)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(UPCOMING_ENTITY_ID)
    assert hass.states.get(UPCOMING_ENTITY_ID).state == "1"

    # state to unavailable
    mock_sonarr.async_get_calendar.side_effect = ArrException

    future = now + timedelta(minutes=1)
    freezer.move_to(future)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    assert hass.states.get(UPCOMING_ENTITY_ID)
    assert hass.states.get(UPCOMING_ENTITY_ID).state == STATE_UNAVAILABLE

    # state to available
    mock_sonarr.async_get_calendar.side_effect = None

    future += timedelta(minutes=1)
    freezer.move_to(future)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    assert hass.states.get(UPCOMING_ENTITY_ID)
    assert hass.states.get(UPCOMING_ENTITY_ID).state == "1"

    # state to unavailable
    mock_sonarr.async_get_calendar.side_effect = ArrException

    future += timedelta(minutes=1)
    freezer.move_to(future)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    assert hass.states.get(UPCOMING_ENTITY_ID)
    assert hass.states.get(UPCOMING_ENTITY_ID).state == STATE_UNAVAILABLE

    # state to available
    mock_sonarr.async_get_calendar.side_effect = None

    future += timedelta(minutes=1)
    freezer.move_to(future)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    assert hass.states.get(UPCOMING_ENTITY_ID)
    assert hass.states.get(UPCOMING_ENTITY_ID).state == "1"
