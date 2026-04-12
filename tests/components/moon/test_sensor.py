"""Tests for the moon sensor platform."""

from __future__ import annotations

from datetime import datetime
from math import degrees

from astral import moon as astral_moon
import ephem
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.moon.const import (
    PHASE_OPTIONS,
    STATE_FIRST_QUARTER,
    STATE_FULL_MOON,
    STATE_LAST_QUARTER,
    STATE_NEW_MOON,
    STATE_WANING_CRESCENT,
    STATE_WANING_GIBBOUS,
    STATE_WAXING_CRESCENT,
    STATE_WAXING_GIBBOUS,
)
from homeassistant.components.sensor import (
    ATTR_OPTIONS,
    ATTR_STATE_CLASS,
    SensorDeviceClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    DEGREE,
    PERCENTAGE,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


def _phase_state(value: float) -> str:
    """Convert an Astral moon phase value to the expected state."""
    if value < 0.5 or value > 27.5:
        return STATE_NEW_MOON
    if value < 6.5:
        return STATE_WAXING_CRESCENT
    if value < 7.5:
        return STATE_FIRST_QUARTER
    if value < 13.5:
        return STATE_WAXING_GIBBOUS
    if value < 14.5:
        return STATE_FULL_MOON
    if value < 20.5:
        return STATE_WANING_GIBBOUS
    if value < 21.5:
        return STATE_LAST_QUARTER
    return STATE_WANING_CRESCENT


def _to_datetime(value: ephem.Date) -> datetime:
    """Convert an ephem date to a UTC datetime."""
    return value.datetime().replace(tzinfo=dt_util.UTC)


@pytest.mark.parametrize(
    ("moon_value", "native_value"),
    [
        (0, STATE_NEW_MOON),
        (5, STATE_WAXING_CRESCENT),
        (7, STATE_FIRST_QUARTER),
        (12, STATE_WAXING_GIBBOUS),
        (14.3, STATE_FULL_MOON),
        (20.1, STATE_WANING_GIBBOUS),
        (20.8, STATE_LAST_QUARTER),
        (23, STATE_WANING_CRESCENT),
    ],
)
def test_moon_phase_state(moon_value: float, native_value: str) -> None:
    """Test moon phase mapping."""
    assert _phase_state(moon_value) == native_value


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_moon_sensors(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Moon sensors."""
    utc_now = datetime(2026, 4, 10, 8, 0, 0, tzinfo=dt_util.UTC)
    freezer.move_to(utc_now)

    observer = ephem.Observer()
    observer.lat = str(hass.config.latitude)
    observer.lon = str(hass.config.longitude)
    observer.elevation = hass.config.elevation
    observer.date = utc_now
    current_moon = ephem.Moon(observer)

    expected_phase = _phase_state(astral_moon.phase(dt_util.now().date()))
    expected_next_rising = _to_datetime(observer.next_rising(ephem.Moon()))
    expected_next_setting = _to_datetime(observer.next_setting(ephem.Moon()))
    expected_next_new_moon = _to_datetime(ephem.next_new_moon(observer.date))
    expected_next_first_quarter_moon = _to_datetime(
        ephem.next_first_quarter_moon(observer.date)
    )
    expected_next_full_moon = _to_datetime(ephem.next_full_moon(observer.date))
    expected_next_last_quarter_moon = _to_datetime(
        ephem.next_last_quarter_moon(observer.date)
    )
    expected_next_transit = _to_datetime(observer.next_transit(ephem.Moon()))
    expected_elevation = degrees(float(current_moon.alt))
    expected_azimuth = degrees(float(current_moon.az))

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    phase_state = hass.states.get("sensor.moon_phase")
    assert phase_state
    assert phase_state.state == expected_phase
    assert phase_state.attributes[ATTR_FRIENDLY_NAME] == "Moon Phase"
    assert phase_state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENUM
    assert phase_state.attributes[ATTR_OPTIONS] == PHASE_OPTIONS

    illumination_state = hass.states.get("sensor.moon_illumination")
    assert illumination_state
    assert float(illumination_state.state) == pytest.approx(current_moon.phase, abs=0.1)
    assert illumination_state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE

    next_rising_state = hass.states.get("sensor.moon_next_rising")
    assert next_rising_state
    assert expected_next_rising.replace(microsecond=0) == dt_util.parse_datetime(
        next_rising_state.state
    )

    next_setting_state = hass.states.get("sensor.moon_next_setting")
    assert next_setting_state
    assert expected_next_setting.replace(microsecond=0) == dt_util.parse_datetime(
        next_setting_state.state
    )

    next_new_moon_state = hass.states.get("sensor.moon_next_new_moon")
    assert next_new_moon_state
    assert expected_next_new_moon.replace(microsecond=0) == dt_util.parse_datetime(
        next_new_moon_state.state
    )

    next_first_quarter_moon_state = hass.states.get(
        "sensor.moon_next_first_quarter_moon"
    )
    assert next_first_quarter_moon_state
    assert expected_next_first_quarter_moon.replace(
        microsecond=0
    ) == dt_util.parse_datetime(next_first_quarter_moon_state.state)

    next_full_moon_state = hass.states.get("sensor.moon_next_full_moon")
    assert next_full_moon_state
    assert expected_next_full_moon.replace(microsecond=0) == dt_util.parse_datetime(
        next_full_moon_state.state
    )

    next_last_quarter_moon_state = hass.states.get("sensor.moon_next_last_quarter_moon")
    assert next_last_quarter_moon_state
    assert expected_next_last_quarter_moon.replace(
        microsecond=0
    ) == dt_util.parse_datetime(next_last_quarter_moon_state.state)

    next_transit_state = hass.states.get("sensor.moon_next_transit")
    assert next_transit_state
    assert expected_next_transit.replace(microsecond=0) == dt_util.parse_datetime(
        next_transit_state.state
    )

    elevation_state = hass.states.get("sensor.moon_elevation")
    assert elevation_state
    assert float(elevation_state.state) == pytest.approx(expected_elevation, abs=0.01)
    assert elevation_state.attributes[ATTR_STATE_CLASS] == "measurement"
    assert elevation_state.attributes[ATTR_UNIT_OF_MEASUREMENT] == DEGREE

    azimuth_state = hass.states.get("sensor.moon_azimuth")
    assert azimuth_state
    assert float(azimuth_state.state) == pytest.approx(expected_azimuth, abs=0.01)
    assert azimuth_state.attributes[ATTR_STATE_CLASS] == "measurement"
    assert azimuth_state.attributes[ATTR_UNIT_OF_MEASUREMENT] == DEGREE

    phase_entry = entity_registry.async_get("sensor.moon_phase")
    assert phase_entry
    assert phase_entry.unique_id == mock_config_entry.entry_id
    assert phase_entry.translation_key == "phase"

    illumination_entry = entity_registry.async_get("sensor.moon_illumination")
    assert illumination_entry
    assert illumination_entry.unique_id == f"{mock_config_entry.entry_id}-illumination"
    assert illumination_entry.translation_key == "illumination"
    assert illumination_entry.entity_category is EntityCategory.DIAGNOSTIC

    next_rising_entry = entity_registry.async_get("sensor.moon_next_rising")
    assert next_rising_entry
    assert next_rising_entry.unique_id == f"{mock_config_entry.entry_id}-next_rising"
    assert next_rising_entry.translation_key == "next_rising"
    assert next_rising_entry.entity_category is EntityCategory.DIAGNOSTIC

    next_setting_entry = entity_registry.async_get("sensor.moon_next_setting")
    assert next_setting_entry
    assert next_setting_entry.unique_id == f"{mock_config_entry.entry_id}-next_setting"
    assert next_setting_entry.translation_key == "next_setting"
    assert next_setting_entry.entity_category is EntityCategory.DIAGNOSTIC

    next_new_moon_entry = entity_registry.async_get("sensor.moon_next_new_moon")
    assert next_new_moon_entry
    assert (
        next_new_moon_entry.unique_id == f"{mock_config_entry.entry_id}-next_new_moon"
    )
    assert next_new_moon_entry.translation_key == "next_new_moon"
    assert next_new_moon_entry.entity_category is EntityCategory.DIAGNOSTIC

    next_first_quarter_moon_entry = entity_registry.async_get(
        "sensor.moon_next_first_quarter_moon"
    )
    assert next_first_quarter_moon_entry
    assert (
        next_first_quarter_moon_entry.unique_id
        == f"{mock_config_entry.entry_id}-next_first_quarter_moon"
    )
    assert next_first_quarter_moon_entry.translation_key == "next_first_quarter_moon"
    assert next_first_quarter_moon_entry.entity_category is EntityCategory.DIAGNOSTIC

    next_full_moon_entry = entity_registry.async_get("sensor.moon_next_full_moon")
    assert next_full_moon_entry
    assert (
        next_full_moon_entry.unique_id == f"{mock_config_entry.entry_id}-next_full_moon"
    )
    assert next_full_moon_entry.translation_key == "next_full_moon"
    assert next_full_moon_entry.entity_category is EntityCategory.DIAGNOSTIC

    next_last_quarter_moon_entry = entity_registry.async_get(
        "sensor.moon_next_last_quarter_moon"
    )
    assert next_last_quarter_moon_entry
    assert (
        next_last_quarter_moon_entry.unique_id
        == f"{mock_config_entry.entry_id}-next_last_quarter_moon"
    )
    assert next_last_quarter_moon_entry.translation_key == "next_last_quarter_moon"
    assert next_last_quarter_moon_entry.entity_category is EntityCategory.DIAGNOSTIC

    next_transit_entry = entity_registry.async_get("sensor.moon_next_transit")
    assert next_transit_entry
    assert next_transit_entry.unique_id == f"{mock_config_entry.entry_id}-next_transit"
    assert next_transit_entry.translation_key == "next_transit"
    assert next_transit_entry.entity_category is EntityCategory.DIAGNOSTIC

    elevation_entry = entity_registry.async_get("sensor.moon_elevation")
    assert elevation_entry
    assert elevation_entry.unique_id == f"{mock_config_entry.entry_id}-elevation"
    assert elevation_entry.translation_key == "elevation"
    assert elevation_entry.entity_category is EntityCategory.DIAGNOSTIC

    azimuth_entry = entity_registry.async_get("sensor.moon_azimuth")
    assert azimuth_entry
    assert azimuth_entry.unique_id == f"{mock_config_entry.entry_id}-azimuth"
    assert azimuth_entry.translation_key == "azimuth"
    assert azimuth_entry.entity_category is EntityCategory.DIAGNOSTIC

    assert phase_entry.device_id
    device_entry = device_registry.async_get(phase_entry.device_id)
    assert device_entry
    assert device_entry.name == "Moon"
    assert device_entry.entry_type is dr.DeviceEntryType.SERVICE
