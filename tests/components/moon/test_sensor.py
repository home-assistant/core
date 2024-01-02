"""The test for the moon sensor platform."""
from __future__ import annotations

import datetime
from datetime import timedelta

from freezegun import freeze_time
import pytest

from homeassistant.components.moon import (
    STATE_FIRST_QUARTER,
    STATE_FULL_MOON,
    STATE_LAST_QUARTER,
    STATE_NEW_MOON,
    STATE_WANING_CRESCENT,
    STATE_WANING_GIBBOUS,
    STATE_WAXING_CRESCENT,
    STATE_WAXING_GIBBOUS,
)
from homeassistant.components.moon.sensor import MOON_ICONS
from homeassistant.components.sensor import ATTR_OPTIONS, SensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_FRIENDLY_NAME, ATTR_ICON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("days_offset", "native_value", "icon"),
    [
        (0, STATE_NEW_MOON, MOON_ICONS[STATE_NEW_MOON]),
        (3, STATE_WAXING_CRESCENT, MOON_ICONS[STATE_WAXING_CRESCENT]),
        (7, STATE_FIRST_QUARTER, MOON_ICONS[STATE_FIRST_QUARTER]),
        (10, STATE_WAXING_GIBBOUS, MOON_ICONS[STATE_WAXING_GIBBOUS]),
        (14, STATE_FULL_MOON, MOON_ICONS[STATE_FULL_MOON]),
        (17, STATE_WANING_GIBBOUS, MOON_ICONS[STATE_WANING_GIBBOUS]),
        (22, STATE_LAST_QUARTER, MOON_ICONS[STATE_LAST_QUARTER]),
        (25, STATE_WANING_CRESCENT, MOON_ICONS[STATE_WANING_CRESCENT]),
    ],
)
async def test_moon_day(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    days_offset: int,
    native_value: str,
    icon: str,
) -> None:
    """Test the Moon sensor."""
    mock_config_entry.add_to_hass(hass)

    now = datetime.datetime(2024, 1, 11, 12, 0, 0, tzinfo=dt_util.UTC) + timedelta(
        days=days_offset
    )
    with freeze_time(now):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.moon_phase")
    assert state
    assert state.state == native_value
    assert state.attributes[ATTR_ICON] == icon
    assert state.attributes[ATTR_FRIENDLY_NAME] == "Moon Phase"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENUM
    assert state.attributes[ATTR_OPTIONS] == [
        STATE_NEW_MOON,
        STATE_WAXING_CRESCENT,
        STATE_FIRST_QUARTER,
        STATE_WAXING_GIBBOUS,
        STATE_FULL_MOON,
        STATE_WANING_GIBBOUS,
        STATE_LAST_QUARTER,
        STATE_WANING_CRESCENT,
    ]

    entry = entity_registry.async_get("sensor.moon_phase")
    assert entry
    assert entry.unique_id == mock_config_entry.entry_id
    assert entry.translation_key == "phase"

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.name == "Moon"
    assert device_entry.entry_type is dr.DeviceEntryType.SERVICE
