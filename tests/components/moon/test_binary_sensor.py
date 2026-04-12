"""Tests for the moon binary sensor platform."""

from __future__ import annotations

from datetime import datetime

import ephem
from freezegun.api import FrozenDateTimeFactory

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


async def test_moon_above_horizon_binary_sensor(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the moon above horizon binary sensor."""
    utc_now = datetime(2026, 4, 10, 8, 0, 0, tzinfo=dt_util.UTC)
    freezer.move_to(utc_now)

    observer = ephem.Observer()
    observer.lat = str(hass.config.latitude)
    observer.lon = str(hass.config.longitude)
    observer.elevation = hass.config.elevation
    observer.date = utc_now
    current_moon = ephem.Moon(observer)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.moon_above_horizon")
    assert state
    assert state.state == ("on" if float(current_moon.alt) > 0 else "off")

    entry = entity_registry.async_get("binary_sensor.moon_above_horizon")
    assert entry
    assert entry.unique_id == f"{mock_config_entry.entry_id}-above_horizon"
    assert entry.translation_key == "above_horizon"

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.name == "Moon"
    assert device_entry.entry_type is dr.DeviceEntryType.SERVICE
